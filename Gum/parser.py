import inspect

from .nodes import *
from .tokens import Tokens
from .custom_types import t_function, t_any, t_list, t_dict
from . import extensions
import sys
import os


class Parser:
    def __init__(self, tokens, file=None):
        self.current_token_index = 0
        self.tokens = tokens if isinstance(tokens, Tokens) else Tokens(tokens, file)
        self.lines = self.tokens.lines
        self.tokens.file = file if file else ""
        self.current_token = self.tokens[0] if len(self.tokens) > 0 else ("EOF", None, -1, -1)
        self.symbol_table = {}
        self.function_table = {}
        self.imports = []
        self.classes = {}
        self.loaded_extensions = {}  # module_name -> extension manifest dict

    def _peek(self):
        if self.current_token_index < len(self.tokens):
            return self.tokens[self.current_token_index]
        return "EOF", None, -1, -1

    def _advance(self):
        self.current_token_index += 1
        self.current_token = self._peek()

    def _back(self):
        self.current_token_index -= 1
        self.current_token = self._peek()

    def _perror(self, error):
        def _print(text):
            print(text, file=sys.stderr)

        if self.current_token == ("EOF", None, -1):
            self.current_token = ("", "", 0)
        line_number = self.current_token[2]
        line = self.lines[line_number - 1].strip()
        col = self.current_token[3]
        _print(f"Traceback:")
        _print(f"  File \"{os.path.abspath(self.tokens.file)}\", line {line_number}, in <module>")
        _print(f"    {line}")
        _print(f"    " + ("~" * col) + ("^" * len(self.current_token[1])))
        _print(error)
        sys.exit(1)

    def _expect(self, tok_type, tok_val=None):
        ttype, tval, _, _ = self.current_token
        if ttype != tok_type or (tok_val is not None and tval != tok_val):
            self._perror(f"Expected token {tok_type} '{tok_val}', got {ttype} '{tval}'")
        self._advance()

    def _common_type(self, types):
        """
        Returns one common type when every item has the same type.
        Otherwise returns t_any.
        """
        types = [type_ for type_ in types if type_ is not None]

        if not types:
            return t_any

        first = types[0]

        if all(type_ == first for type_ in types):
            return first

        return t_any

    def _make_index_access(self, base, index):
        node = IndexAccessNode(base, index, False, None)

        base_type = self.infer_type(base)
        inferred_type = t_any

        if isinstance(base_type, t_list):
            # List<T>::operator[] already returns T, so no any_cast.
            inferred_type = base_type.item_type

        elif isinstance(base_type, t_dict):
            # Dict::operator[] returns std::any.

            if isinstance(index, StringNode):
                inferred_type = base_type.field_type(index.value)
            else:
                inferred_type = base_type.value_type

        elif base_type is list:
            # Old/untyped list.
            inferred_type = t_any

        elif base_type is dict:
            # Old/untyped dictionary.
            inferred_type = t_any

        node.inferred_type = inferred_type

        return node

    def _iterable_item_type(self, iterable):
        if isinstance(iterable, RangeNode):
            return int

        iterable_type = self.infer_type(iterable)
        if isinstance(iterable_type, t_list):
            return iterable_type.item_type
        if iterable_type is list:
            return t_any

        return t_any

    def parse(self):
        statements = []
        while self.current_token[0] != "EOF":
            stmt = self.parse_statement()
            statements.append(stmt)
        return ProgramNode(statements)

    def parse_statement(self):
        ttype, tval, _, _ = self.current_token
        if ttype == "KEYWORD":
            if tval == "let":
                return self.parse_let()
            elif tval == "def":
                return self.parse_function_def()
            elif tval == "object":
                return self.parse_object()
            elif tval == "return":
                return self.parse_return()
            elif tval == "if":
                return self.parse_if()
            elif tval == "while":
                return self.parse_while()
            elif tval == "for":
                return self.parse_for()
            elif tval == "import":
                return self.parse_import()
        return self.parse_expression_statement()

    def parse_import(self):
        self._expect("KEYWORD", "import")
        var_name = self.current_token[1]
        self._expect("IDENTIFIER")
        self.imports.append(var_name)

        # If this import resolves to a native extension (rather than a
        # plain .gum file import), register its functions' return types so
        # `let x = someExtensionFunc(...)` infers correctly, the same way
        # calls to builtins already do via self.function_table.
        ext = extensions.load_extension(self.tokens.file, var_name)
        if ext:
            self.loaded_extensions[var_name] = ext
            for func_name, sig in ext["functions"].items():
                self.function_table[func_name] = sig.get("return")

        return ImportNode(var_name)

    def parse_for(self):
        self._expect("KEYWORD", "for")

        var_name = self.current_token[1]
        self._expect("IDENTIFIER")

        self._expect("KEYWORD", "in")

        # Parse start or iterable expression
        iterable_expr = self.parse_expression()

        # Check for range operator (-> or =>)
        if self.current_token[0] == "OPERATOR" and self.current_token[1] in ("->", "=>"):
            op = self.current_token[1]
            inclusive = op == "=>"
            self._advance()

            end_expr = self.parse_expression()

            iterable_expr = RangeNode(iterable_expr, end_expr, inclusive)

        loop_var_previous = self.symbol_table.get(var_name, None)
        loop_var_existed = var_name in self.symbol_table
        self.symbol_table[var_name] = self._iterable_item_type(iterable_expr)

        # Parse loop body
        self._expect("SYMBOL", "{")
        body = self.parse_block()
        self._expect("SYMBOL", "}")

        if loop_var_existed:
            self.symbol_table[var_name] = loop_var_previous
        else:
            self.symbol_table.pop(var_name, None)

        return ForNode(var_name, iterable_expr, body)

    def parse_while(self):
        self._expect("KEYWORD", "while")

        condition = self.parse_expression()

        self._expect("SYMBOL", "{")
        body = self.parse_block()
        self._expect("SYMBOL", "}")

        return WhileNode(condition, body)

    def parse_if(self):
        self._expect("KEYWORD", "if")

        condition = self.parse_expression()  # This must consume a > b
        self._expect("SYMBOL", "{")  # This expects '{' immediately after condition

        body = self.parse_block()
        self._expect("SYMBOL", "}")

        elif_blocks = []
        while self.current_token[0] == "KEYWORD" and self.current_token[1] == "elif":
            self._advance()
            elif_cond = self.parse_expression()
            self._expect("SYMBOL", "{")
            elif_body = self.parse_block()
            self._expect("SYMBOL", "}")
            elif_blocks.append((elif_cond, elif_body))

        else_body = None
        if self.current_token[0] == "KEYWORD" and self.current_token[1] == "else":
            self._advance()
            self._expect("SYMBOL", "{")
            else_body = self.parse_block()
            self._expect("SYMBOL", "}")

        return IfNode(condition, body, elif_blocks, else_body)

    def parse_let(self):
        self._expect("KEYWORD", "let")

        if self.current_token[0] != "IDENTIFIER":
            self._perror("Expected variable name after 'let'")
        var_name = self.parse_variable_name()
        if isinstance(var_name, IndexAccessNode):
            self._perror("Cannot assign value to indexed variable with 'let'")

        var_type = None
        if self.current_token[0] == "SYMBOL" and self.current_token[1] == ":":
            self._advance()
            if self.current_token[0] != "IDENTIFIER":
                self._perror("Expected type name after ':'")
            var_type = self.evaluate_type_from_string(self.parse_variable_name())

        self._expect("OPERATOR", "=")
        value = self.parse_expression()

        if not var_type:  # We will try to guess the type by what we are assigning
            var_type = self.infer_type(value)
        elif isinstance(var_type, t_dict) and isinstance(value, DictNode):
            inferred_type = self.infer_type(value)
            if isinstance(inferred_type, t_dict):
                var_type = inferred_type

        if (
                isinstance(value, IndexAccessNode)
                and (
                    isinstance(getattr(value, "container_type", None), t_dict)
                    or isinstance(value.index_expr, StringNode)
                )
                and getattr(value, "inferred_type", t_any) in (None, t_any)
                and var_type not in (None, t_any)
        ):
            value.inferred_type = var_type
            value.requires_any_cast = True

        self.symbol_table[var_name.var_name] = var_type

        return AssignmentNode(var_name, value, var_type)

    def _record_index_assignment(self, target, value):
        container_type = self.infer_type(target.var_name)
        value_type = self.infer_type(value) or t_any

        if not isinstance(container_type, t_dict):
            return

        target.container_type = container_type
        target.inferred_type = value_type
        target.requires_any_cast = True

        if isinstance(target.index_expr, StringNode):
            container_type.fields[target.index_expr.value] = value_type
            container_type.value_type = self._common_type(container_type.fields.values())
        else:
            container_type.value_type = self._common_type([
                container_type.value_type,
                value_type,
            ])

    def evaluate_type_from_string(self, string):
        # parse_variable_name() now returns a VarAccessNode (so it can
        # support dotted names like `WidgetPacket.Widget`), so unwrap it
        # back down to the plain dotted string before comparing/using it.
        if isinstance(string, VarAccessNode):
            string = string.var_name

        if string == "int":
            return int
        elif string == "str":
            return str
        elif string == "float":
            return float
        elif string == "list":
            return list
        elif string == "bool":
            return bool
        elif string == "dict":
            return t_dict()
        elif string == "any":
            return t_any

        # Dotted type name referring to a module import, e.g.
        # `WidgetPacket.Widget` -> the transpiled C++ needs the
        # namespace-qualified `WidgetPacket::Widget`.
        if isinstance(string, str) and "." in string:
            parts = string.split(".")
            if parts[0] in self.imports:
                return "::".join(parts)

        return string

    def parse_return(self):
        self._expect("KEYWORD", "return")
        expr = self.parse_expression()
        return ReturnNode(expr)

    def parse_variable_name(self):
        if self.current_token[0] != "IDENTIFIER":
            frame = inspect.stack()[1]
            line = frame.code_context[0].strip() if frame.code_context else "<no source>"
            print(f"[parse_variable_name called from {frame.function}() at line {frame.lineno}: {line}]",
                  file=sys.stderr)
            self._perror("Expected variable name")

        name_parts = [self.current_token[1]]
        self._advance()

        while self.current_token[0] == "SYMBOL" and self.current_token[1] == ".":
            self._advance()
            if self.current_token[0] != "IDENTIFIER":
                self._perror("Expected identifier after '.'")
            name_parts.append(self.current_token[1])
            self._advance()

        base = VarAccessNode(".".join(name_parts))

        # Handle list indexing, like arr[1][2]
        while self.current_token[0] == "SYMBOL" and self.current_token[1] == "[":
            self._advance()
            index_expr = self.parse_expression()
            self._expect("SYMBOL", "]")
            base = self._make_index_access(base, index_expr)

        return base

    def parse_function_def(self):
        ret = None

        self._expect("KEYWORD", "def")

        if self.current_token[0] != "IDENTIFIER":
            self._perror("Expected function name after 'def'")
        func_name = self.current_token[1]
        self._advance()

        self._expect("SYMBOL", "(")
        params = self.parse_parameters()
        self._expect("SYMBOL", ")")

        if self.current_token[0] == "SYMBOL" and self.current_token[1] == ":":
            self._advance()
            if self.current_token[0] != "IDENTIFIER":
                self._perror("Expected type name after ':' after function def")
            ret = self.evaluate_type_from_string(self.parse_variable_name())

        template = False
        if self.current_token[0] == "KEYWORD" and self.current_token[1] == "template":
            self._advance()
            template = True

        self._expect("SYMBOL", "{")
        safe = self.symbol_table.copy()
        for name, type_, _ in params:
            self.symbol_table[name] = type_
        body = self.parse_block()
        self.symbol_table = safe.copy()
        self._expect("SYMBOL", "}")

        params = self.infer_param_types_from_body(body, params)

        return_type = ret if ret else self.infer_return_type_from_body(body, params)
        self.function_table[func_name] = return_type

        return FunctionDefNode(func_name, params, body, return_type, template)

    def infer_param_types_from_body(self, body, params):
        param_names = {name for name, ptype, pdefault in params if ptype is None}
        if not param_names:
            return params

        safe = self.symbol_table.copy()
        for name, type_, _ in params:
            self.symbol_table[name] = type_

        evidence = {name: [] for name in param_names}

        def note(name, type_):
            if type_ is not None and name in evidence:
                evidence[name].append(type_)

        def safe_infer(node):
            try:
                return self.infer_type(node)
            except Exception:
                return None

        def is_param(node, name=None):
            return isinstance(node, VarAccessNode) and (
                node.var_name in param_names if name is None else node.var_name == name)

        def walk(node, skip_names=frozenset()):
            if node is None:
                return
            if isinstance(node, (list, tuple)):
                for item in node:
                    walk(item, skip_names)
                return
            if isinstance(node, dict):
                for k, v in node.items():
                    walk(k, skip_names)
                    walk(v, skip_names)
                return
            if not isinstance(node, ASTNode):
                return  # NumberNode's .value, strings, bools, type objects, etc.

            # --- pattern matches ---
            if isinstance(node, BinOpNode):
                left, right = node.left, node.right
                if is_param(left) and left.var_name not in skip_names:
                    other = safe_infer(right)
                    if other:
                        note(left.var_name, other)
                if is_param(right) and right.var_name not in skip_names:
                    other = safe_infer(left)
                    if other:
                        note(right.var_name, other)

            elif isinstance(node, ModifiedAssignmentNode):
                target, value = node.var_name, node.value
                if is_param(target) and target.var_name not in skip_names:
                    other = safe_infer(value)
                    if other:
                        note(target.var_name, other)

            elif isinstance(node, IndexAccessNode):
                base, index = node.var_name, node.index_expr
                if is_param(base) and base.var_name not in skip_names:
                    note(base.var_name, list)
                if is_param(index) and index.var_name not in skip_names:
                    note(index.var_name, int)

            elif isinstance(node, ForNode):
                if is_param(node.iterable) and node.iterable.var_name not in skip_names:
                    note(node.iterable.var_name, list)

            elif isinstance(node, RangeNode):
                for side in (node.start, node.end):
                    if is_param(side) and side.var_name not in skip_names:
                        note(side.var_name, int)

            elif isinstance(node, MethodCallNode):
                caller = node.caller
                if is_param(caller) and caller.var_name not in skip_names:
                    str_methods = {"upper", "lower", "strip", "split", "replace"}
                    list_methods = {"append", "pop", "extend", "insert"}
                    if node.method_name in str_methods:
                        note(caller.var_name, str)
                    elif node.method_name in list_methods:
                        note(caller.var_name, list)

            elif isinstance(node, (IfNode, WhileNode)):
                cond = node.condition
                if is_param(cond) and cond.var_name not in skip_names:
                    note(cond.var_name, bool)

            elif isinstance(node, FunctionDefNode):
                # nested/lambda def — don't let its own params shadow ours
                shadowed = skip_names | {n for n, _, _ in node.params}
                for stmt in node.body:
                    walk(stmt, shadowed)
                return  # already recursed manually, don't fall through

            # generic recursion into every attribute
            for value in vars(node).values():
                walk(value, skip_names)

        for stmt in body:
            walk(stmt)

        self.symbol_table = safe.copy()

        resolved = []
        for name, declared, default in params:
            if declared is not None:
                resolved.append((name, declared, default))
                continue
            candidates = evidence.get(name, [])
            if candidates and all(t == candidates[0] for t in candidates):
                resolved.append((name, candidates[0], default))
            else:
                resolved.append((name, t_any, default))
        return resolved

    def infer_return_type_from_body(self, body, params=None):
        types = []

        has_return = False

        for stmt in body:
            if isinstance(stmt, ReturnNode):
                has_return = True
                inferred = self.infer_type(stmt.value)
                if inferred:
                    types.append(inferred)
                elif params:
                    safe = self.symbol_table.copy()
                    for name, type_, _ in params:
                        self.symbol_table[name] = type_
                    inferred = self.infer_type(stmt.value)
                    if inferred:
                        types.append(inferred)
                    self.symbol_table = safe.copy()
            elif isinstance(stmt, IfNode):
                # Infer from all branches
                types.append(self.infer_return_type_from_body(stmt.body, params=params))
                for _, elif_body in stmt.elif_blocks:
                    types.append(self.infer_return_type_from_body(elif_body, params=params))
                if stmt.else_body:
                    types.append(self.infer_return_type_from_body(stmt.else_body, params=params))
            elif isinstance(stmt, WhileNode):
                # Some functions return inside loops
                types.append(self.infer_return_type_from_body(stmt.body, params=params))
            # Add more cases if needed (e.g., for blocks inside objects)

        # Flatten nested lists
        flat = []
        for t in types:
            if isinstance(t, list):
                flat.extend(t)
            elif t is not None:
                flat.append(t)

        # Pick most common type or None if unsure
        if not flat:
            if has_return:
                return None
            else:
                return "void"
        if all(t == flat[0] for t in flat):
            return flat[0]
        else:
            raise SyntaxError("A function cannot have multiple return types")

    def infer_type(self, node):
        if node is None:
            return None
        if isinstance(node, NumberNode):
            return type(node.value)
        if isinstance(node, StringNode):
            return str
        if isinstance(node, BooleanNode):
            return bool
        if isinstance(node, NullNode):
            return t_any
        if isinstance(node, VarAccessNode):
            return self.symbol_table.get(node.var_name)
        if isinstance(node, FunctionCallNode):
            name = node.func_name
            if name in self.classes:
                return name
            return self.function_table.get(name)
        if isinstance(node, ListNode):
            return t_list(node.inferred_type or t_any)
        if isinstance(node, DictNode):
            return getattr(
                node,
                "inferred_type",
                t_dict(),
            )
        if isinstance(node, IndexAccessNode):
            existing = getattr(node, "inferred_type", None)
            if existing is not None:
                return existing
            base_type = self.infer_type(node.var_name)
            if isinstance(base_type, t_list):
                inferred = base_type.item_type
            elif isinstance(base_type, t_dict):
                if isinstance(node.index_expr, StringNode):
                    inferred = base_type.field_type(
                        node.index_expr.value
                    )
                else:
                    inferred = base_type.value_type
            else:
                inferred = t_any
            node.inferred_type = inferred
            return inferred
        if isinstance(node, UnaryOpNode):
            return self.infer_type(node.operand)
        if isinstance(node, BinOpNode):
            left = self.infer_type(node.left)
            right = self.infer_type(node.right)
            comparison_operators = {
                "==",
                "!=",
                "<",
                ">",
                "<=",
                ">=",
            }
            if node.operator in comparison_operators:
                return bool
            if node.operator == "/":
                if left in (int, float) and right in (int, float):
                    return float
            if left == right:
                return left
            if left is str or right is str:
                return str
            if left is float or right is float:
                return float
            if left is int or right is int:
                return int
            return t_any
        return getattr(node, "inferred_type", None)

    def parse_parameters(self):
        params = []
        default_args = False
        while self.current_token[0] != "SYMBOL" or self.current_token[1] != ")":
            param_name = ""
            parameters = None
            if self.current_token[0] == "SYMBOL" and self.current_token[1] == "[":
                self._advance()
                param_name = self.current_token[1]
                self._expect("IDENTIFIER")
                self._expect("SYMBOL", "]")
                self._expect("SYMBOL", "(")
                none_params = self.parse_parameters()
                parameters = []
                for name, type_, default in none_params:
                    if type_ is None:
                        type_ = t_any
                    parameters.append((name, type_, default))
            elif self.current_token[0] != "IDENTIFIER":
                self._perror("Expected parameter name")
            else:
                param_name = self.current_token[1]
            self._advance()

            param_type = None
            if self.current_token[0] == "SYMBOL" and self.current_token[1] == ":":
                self._advance()
                if self.current_token[0] != "IDENTIFIER":
                    self._perror("Expected type name after ':' in parameter")
                param_type = self.parse_variable_name()
            if parameters:
                param_type = t_function(parameters, self.evaluate_type_from_string(param_type))

            default_arg = None
            if self.current_token[0] == "OPERATOR" and self.current_token[1] == "=":
                self._advance()
                default_arg = self.parse_expression()
                if param_type is None:
                    param_type = self.infer_type(default_arg)
                if self.infer_type(default_arg) != self.evaluate_type_from_string(param_type):
                    self._back()
                    self._perror(f"Parameter default type must match defined type.\nExpected '{self.evaluate_type_from_string(param_type).__name__}', got '{self.infer_type(default_arg).__name__}'")
                default_args = True
            elif default_args:
                self._back()
                self._back()
                self._back()
                self._perror("Argument does not have default value")

            params.append((param_name, self.evaluate_type_from_string(param_type), default_arg))

            if self.current_token[0] == "SYMBOL" and self.current_token[1] == ",":
                self._advance()
            else:
                break
        return params

    def parse_block(self):
        statements = []
        while self.current_token[0] != "SYMBOL" or self.current_token[1] != "}":
            stmt = self.parse_statement()
            statements.append(stmt)
        return statements

    def parse_object(self):
        self._expect("KEYWORD", "object")
        if self.current_token[0] != "IDENTIFIER":
            self._perror("Expected object name after 'object'")
        obj_name = self.current_token[1]
        self._advance()

        parent = None
        if self.current_token[0] == "KEYWORD" and self.current_token[1] == "succeeds":
            self._advance()
            if self.current_token[0] != "IDENTIFIER":
                self._perror("Expected object name after 'succeeds' in object definition")
            parent = self.current_token[1]
            if parent not in self.classes:
                self._perror(f"Unknown object '{parent}'")
            self._advance()

        self._expect("SYMBOL", "{")

        methods = []
        while self.current_token[0] != "SYMBOL" or self.current_token[1] != "}":
            if self.current_token[0] == "KEYWORD" and self.current_token[1] == "def":
                methods.append(self.parse_function_def())
            else:
                self._perror("Only method definitions allowed inside an object")

        self._expect("SYMBOL", "}")

        if parent:
            parent_methods = {
                method.func_name: method
                for method in self.classes[parent].methods
            }

            for obj_method in methods:
                if obj_method.func_name in ("construct", "constructor"):
                    continue
                parent_method = parent_methods.get(obj_method.func_name)

                # New method - perfectly valid.
                if parent_method is None:
                    continue

                # Existing method - must be template.
                if not parent_method.template:
                    self._perror(
                        f"Method '{obj_method.func_name}' in '{obj_name}' cannot override "
                        f"non-template method in '{parent}'"
                    )

                # Parameter count must match.
                if len(obj_method.params) != len(parent_method.params):
                    self._perror(
                        f"Method '{obj_method.func_name}' in '{obj_name}' has an "
                        f"incorrect parameter count"
                    )

                # Parameter names/types must match.
                for child_param, parent_param in zip(obj_method.params, parent_method.params):
                    if child_param[0] != parent_param[0] or child_param[1] != parent_param[1]:
                        self._perror(
                            f"Method '{obj_method.func_name}' in '{obj_name}' "
                            f"does not match the parent method signature"
                        )

        node = ClassNode(obj_name, methods, parent_class=parent)
        self.classes[obj_name] = node

        return node

    def parse_expression_statement(self):
        expr = self.parse_expression()
        return expr

    def parse_expression(self, min_prec=0):
        left = self.parse_term()

        precedences = {
            '+=': 1,
            '-=': 1,
            '*=': 1,
            '/=': 1,
            '==': 0,
            '!=': 0,
            '<': 0,
            '>': 0,
            '<=': 0,
            '>=': 0,
            '+': 2,
            '-': 2,
            '*': 3,
            '/': 3,
            '%': 3,
        }

        while self.current_token[0] == "OPERATOR":
            op = self.current_token[1]
            prec = precedences.get(op, -1)
            if prec < min_prec:
                break

            # Assignment operators parse the right side as a term only
            if op in ('+=', '-=', '*=', '/='):
                self._advance()
                right = self.parse_term()
                left = ModifiedAssignmentNode(left, op, right)
            else:
                self._advance()
                right = self.parse_expression(prec + 1)
                left = BinOpNode(left, op, right)

        if self.current_token[0] == "OPERATOR" and self.current_token[1] == "=":
            self._advance()
            if isinstance(left, VarAccessNode):
                if left.var_name in self.symbol_table:
                    left = ModifiedAssignmentNode(left, "=", self.parse_expression())
                else:
                    self._perror("Cannot make a new variable without let")
            elif isinstance(left, IndexAccessNode):
                value = self.parse_expression()
                self._record_index_assignment(left, value)
                left = ModifiedAssignmentNode(left, "=", value)

        return left

    def parse_term(self):
        tok = self.current_token

        if tok[0] == "STRING":
            self._advance()
            return StringNode(tok[1].strip('"'))
        elif tok[0] == "NUMBER":
            self._advance()
            try:
                value = int(tok[1])
            except ValueError:
                value = float(tok[1])
            return NumberNode(value)
        elif tok[0] == "IDENTIFIER":
            return self.parse_identifier_expression()
        elif tok[0] == "SYMBOL":
            if tok[1] == "(":
                self._advance()
                expr = self.parse_expression()
                self._expect("SYMBOL", ")")
                return expr
            if tok[1] == "[":
                self._advance()
                items, inferred_type = self.parse_list()
                self._expect("SYMBOL", "]")
                expr = ListNode(items, inferred_type)
                return expr
            if tok[1] == "{":
                self._advance()
                key_values = self.parse_dict()
                self._expect("SYMBOL", "}")
                node = DictNode(key_values)
                key_types = []
                value_types = []
                fields = {}
                for key_node, value_node in key_values.items():
                    key_type = self.infer_type(key_node)
                    value_type = self.infer_type(value_node)

                    key_types.append(key_type)
                    value_types.append(value_type)

                    if isinstance(key_node, StringNode):
                        fields[key_node.value] = value_type
                node.inferred_type = t_dict(
                    key_type=self._common_type(key_types),
                    value_type=self._common_type(value_types),
                    fields=fields,
                )
                return node
            return None
        elif tok[0] == "BOOLEAN":
            expr = BooleanNode(tok[1] == "true")
            self._advance()
            return expr
        elif tok[0] == "OPERATOR":
            if tok[1] == "-":
                self._advance()  # Consume -
                expr = self.parse_expression()
                return UnaryOpNode("-", expr)
            return None
        elif tok[0] == "NULL":
            self._advance()
            return NullNode()
        else:
            self._perror("Invalid expression")
            return None

    def parse_identifier_expression(self):
        # Start with the first variable
        node = VarAccessNode(self.current_token[1])
        self._advance()

        while True:
            if self.current_token[0] == "SYMBOL":
                if self.current_token[1] == ".":
                    self._advance()
                    if self.current_token[0] != "IDENTIFIER":
                        self._perror("Expected identifier after '.'")
                    attr = self.current_token[1]
                    self._advance()

                    # Check for method call
                    if self.current_token[0] == "SYMBOL" and self.current_token[1] == "(":
                        self._advance()
                        args = self.parse_argument_list()
                        self._expect("SYMBOL", ")")
                        if isinstance(node, VarAccessNode) and node.var_name in self.imports:
                            node = MethodCallNode(ImportModuleVariableNode(node.var_name), attr, args)
                        else:
                            node = MethodCallNode(node, attr, args)
                    else:
                        if isinstance(node, VarAccessNode) and node.var_name in self.imports:
                            node = AttrAccessNode(ImportModuleVariableNode(node.var_name), VarAccessNode(attr))
                        else:
                            node = AttrAccessNode(node, VarAccessNode(attr))

                elif self.current_token[1] == "(":
                    self._advance()
                    args = self.parse_argument_list()
                    self._expect("SYMBOL", ")")
                    node = FunctionCallNode(node.var_name, args)

                elif self.current_token[1] == "[":
                    self._advance()
                    index = self.parse_expression()
                    self._expect("SYMBOL", "]")
                    node = self._make_index_access(node, index)

                else:
                    break
            else:
                break

        return node

    def parse_argument_list(self):
        args = []
        if self.current_token[0] == "SYMBOL" and self.current_token[1] == ")":
            return args
        while True:
            arg = self.parse_expression()
            args.append(arg)
            if self.current_token[0] == "SYMBOL" and self.current_token[1] == ",":
                self._advance()
            else:
                break
        return args

    def parse_list(self):
        items = []
        if self.current_token[0] == "SYMBOL" and self.current_token[1] == "]":
            return items, t_any
        while True:
            item = self.parse_expression()
            items.append(item)
            if self.current_token[0] == "SYMBOL" and self.current_token[1] == ",":
                self._advance()
            else:
                break
        item_types = [
            self.infer_type(item)
            for item in items
        ]
        inferred_type = self._common_type(item_types)
        return items, inferred_type

    def parse_dict(self):
        args = {}
        if self.current_token[0] == "SYMBOL" and self.current_token[1] == "}":
            return args
        while True:
            key = self.parse_expression()
            self._expect("SYMBOL", ":")
            value = self.parse_expression()
            args[key] = value
            if self.current_token[0] == "SYMBOL" and self.current_token[1] == ",":
                self._advance()
            else:
                break
        return args
