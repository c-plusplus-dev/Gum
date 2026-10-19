from .nodes import *
from .custom_types import t_any, t_function, t_list, t_dict
from .parser import Parser
from .lexer import Lexer
import os
import tempfile
import subprocess
from importlib.resources import files

from typing import Any

def _local_abspath(path):
    return os.path.join(os.path.dirname(__file__), path)

def compile_file(filepath, output=None, accessory_file=False, verbose=False) -> tuple[int, Any, str | None]:
    absp = _local_abspath
    try:
        with open(filepath, "r") as f:
            code = f.read()
    except FileNotFoundError:
        print(f"Error: File not found: {filepath}")
        return 1, None, None
    except Exception as e:
        print(f"Error: {e}")
        return 1, None, None

    if not output:
        basename = os.path.basename(filepath)
        if '.' in basename:
            output = ".".join(basename.split(".")[:-1])
        else:
            output = basename + "_out"
        output = os.path.join(
            os.path.dirname(filepath),
            output,
        )
    output = os.path.abspath(output)
    os.makedirs(os.path.dirname(output), exist_ok=True)

    print("gumc [INFO] Lexing...")
    lexer = Lexer()
    tokens = lexer.lex(code)

    print("gumc [INFO] Parsing...")
    parser = Parser(tokens, filepath)
    try:
        program = parser.parse()
    except Exception as e:
        raise e
        print(f"Parse error: {e}")
        return 1, None, None

    print("gumc [INFO] Compiling...")
    compiler = Transpiler(filepath, accessory_file, loaded_extensions=parser.loaded_extensions)
    cpp_code = compiler.transpile(program)

    if accessory_file:
        return 0, None, cpp_code

    main_temp = tempfile.NamedTemporaryFile("w", suffix=".cpp", delete=True)
    header_temp = os.path.join(os.path.dirname(main_temp.name), "gum-builtins.hpp")

    with main_temp.file as f:
        f.write(cpp_code)

    with open(header_temp, "w") as f:
        f.write(files("Gum.templates").joinpath("gum-builtins.hpp").read_text(encoding="utf-8"))

    # Collect anything pulled in by `import <extension>` statements: extra
    # include dirs (so #include "Header.hpp" resolves), extra source files
    # to compile alongside the generated main.cpp, and any frameworks they
    # need linked in.
    include_dirs = []
    extra_sources = []
    frameworks = []
    needs_objcxx_arc = False
    # Always searchable, so extension headers that #include "gum-builtins.hpp"
    # (quote-includes search the including file's own directory first, which
    # for an extension header is the extensions folder, not this temp dir)
    # can still find it.
    include_dirs.append(os.path.dirname(main_temp.name))
    for ext in compiler.loaded_extensions.values():
        ext_dir = str(ext["dir"])
        if ext_dir not in include_dirs:
            include_dirs.append(ext_dir)
        for src in ext["sources"]:
            src = str(src)
            extra_sources.append(src)
            if src.endswith(".mm"):
                needs_objcxx_arc = True
        for fw in ext["frameworks"]:
            if fw not in frameworks:
                frameworks.append(fw)

    command = ["g++", "-std=c++20", "-ferror-limit=0"]
    if verbose: command.append("-v")
    for d in include_dirs:
        command.extend(["-I", d])
    if needs_objcxx_arc:
        command.append("-fobjc-arc")
    command.append(main_temp.name)
    command.extend(extra_sources)
    for fw in frameworks:
        command.extend(["-framework", fw])
    command.extend(["-o", output])
    result = subprocess.run(command)
    if result.returncode != 0:
        print("Compilation failed!")
        return 1, None, cpp_code
    return 0, output, cpp_code

class Transpiler:
    def __init__(self, filepath, accessory = False, loaded_extensions = None):
        self.code = []
        self.indent_level = 0
        self.filepath = filepath
        self.accessory = accessory
        self.functions = []
        self.classes = {}
        self.variables = {} # should have 'a': type
        self.loaded_extensions = loaded_extensions or {}  # module_name -> extension manifest dict
        # Flat func_name -> return-type-string lookup across all imported
        # extensions, so constructor-style call sites (see
        # transpile_ClassNode) can tell an extension function call apart
        # from an actual object constructor without hardcoding names.
        self.extension_function_returns = {
            func_name: sig.get("return")
            for ext in self.loaded_extensions.values()
            for func_name, sig in ext["functions"].items()
        }

    def indent(self):
        return "    " * self.indent_level

    def transpile(self, program):
        return self._transpile(program, {"program": program})

    def _transpile(self, node, kwargs):
        method = getattr(self, f"transpile_{type(node).__name__}", None)
        if not method:
            raise NotImplementedError(f"No transpile_{type(node).__name__}")
        print(f"transpile_{type(node).__name__}")
        return method(node, kwargs)

    def _transpile_stmt(self, node, kwargs):
        out = self._transpile(node, kwargs)
        if isinstance(node, FunctionCallNode):
            self.echo(out + ";")
        if isinstance(node, MethodCallNode):
            self.echo(out + ";")

    def echo(self, string=""):
        self.code.append(self.indent() + string)

    def up(self):
        self.indent_level += 1

    def down(self):
        self.indent_level -= 1

    def transpile_args(self, args, kwargs: dict):
        kwargs.update({"params": True})
        string = ", ".join(self._transpile(arg, kwargs) for arg in args)
        kwargs.pop("params", None)
        return string

    def transpile_params(self, params):
        parameters = []
        for param_name, param_type, default in params:
            if param_name == "this":
                continue
            param_name = param_name.split(".")
            if param_name[0] == "this":
                param_name = param_name[1:]
            param_name = ".".join(param_name)
            if isinstance(param_type, t_function):
                types = [self.transpile_type(pt) for _, pt, _2 in param_type.parameters]
                ret = self.transpile_type(param_type.ret)
                if ret == "auto":
                    ret = "std::any"
                param_type = ret
                param_name = f"(*{param_name})({', '.join(types)})"
            else:
                param_type = self.transpile_type(param_type)
            parameter = f"{param_type} {param_name}"
            if default is not None:
                parameter += f" = {self._transpile(default, {})}"
            parameters.append(parameter)
        return ", ".join(parameters)

    def transpile_type(self, type_):
        if isinstance(type_, str):
            return type_
        if isinstance(type_, t_list):
            return f"ListPtr"
        if isinstance(type_, t_dict):
            return "DictPtr"
        # Backward compatibility with the old [type] representation.
        if isinstance(type_, list):
            return f"ListPtr"
        return {
            int: "int",
            float: "double",
            str: "std::string",
            list: "ListPtr",
            dict: "DictPtr",
            bool: "bool",
            t_any: "Value",
        }.get(type_, "auto")

    def transpile_ProgramNode(self, node, kwargs):
        if not self.accessory:
            self.echo('#include "gum-builtins.hpp"')
            self.echo('using namespace GumCpp;')
            self.echo('')
        else:
            self.echo(f'namespace {os.path.basename(self.filepath).removesuffix(".gum")} {{')
            self.up()

        for stmt in node.statements:
            if isinstance(stmt, ClassNode):
                self._transpile(stmt, kwargs)
            elif isinstance(stmt, FunctionDefNode):
                self._transpile(stmt, kwargs)
            elif isinstance(stmt, ImportNode):
                self._transpile(stmt, kwargs)
        skip = (ClassNode, FunctionDefNode, ImportNode)

        if not self.accessory:
            self.echo('')
            self.echo('int main(int argc, char *argv[]) {')
            self.up()

            for stmt in node.statements:
                if not isinstance(stmt, skip):
                    self._transpile_stmt(stmt, kwargs)

            self.down()
            self.echo('}')
        else:
            self.down()
            self.echo("};")

        return "\n".join(self.code)

    def transpile_ClassNode(self, node: ClassNode, kwargs):
        self.echo(f'class {node.class_name} {f": public {node.parent_class} " if node.parent_class else ""}{{')
        self.echo('public:')
        self.up()

        constructor = next((m for m in node.methods if m.func_name in {"construct", "constructor"}), None)
        if constructor:
            if constructor.params[1:]:
                self.echo(f"{node.class_name}() = default;")
            variables = []
            for stmt in constructor.body:
                if isinstance(stmt, AssignmentNode):
                    type_ = self.transpile_type(stmt.var_type)
                    if type_ == "auto":
                        if isinstance(stmt.value, ListNode):
                            type_ = f"List<{self.transpile_type(stmt.value.inferred_type)}>"
                        elif isinstance(stmt.value, FunctionCallNode):
                            # Try making it a class call (will not always work but eh) but also check for
                            # extension functions first, since those aren't constructors.
                            func_name = stmt.value.func_name
                            if func_name in self.extension_function_returns:
                                type_ = self.extension_function_returns[func_name]
                            else:
                                type_ = func_name
                    variables.append(stmt)
                    self.echo(f"{type_} {self._transpile(stmt.var_name, kwargs)};")
            self.echo(f'{node.class_name}({self.transpile_params(constructor.params)}) {{')
            self.up()

            kwargs.update({"class_vars": variables})
            for stmt in constructor.body:
                self._transpile_stmt(stmt, kwargs)
            kwargs.pop("class_vars")

            self.down()
            self.echo('}')
        else:
            self.echo(f"{node.class_name}() = default;")

        print_func = next((m for m in node.methods if m.func_name in {"__print"}), None)
        if print_func:
            self.echo(
                f"{self.transpile_type(print_func.return_type)} {print_func.func_name}({self.transpile_params(print_func.params)}) const {{")
            self.up()

            kwargs.update({"func": print_func})
            for stmt in print_func.body:
                if isinstance(stmt, FunctionDefNode):
                    self.transpile_lambda(stmt, kwargs)
                    continue
                self._transpile_stmt(stmt, kwargs)
            kwargs.pop("func")

            self.down()
            self.echo('}')

            self.echo(f"friend std::ostream& operator<<(std::ostream& os, const {node.class_name}& obj) {{\n")
            self.up()
            self.echo(f"os << obj.__print();\n")
            self.echo(f"return os;\n")
            self.down()
            self.echo('}')

        kwargs.update({"class": node})
        for method in node.methods:
            if method.func_name not in {"construct", "constructor", "__print"}:
                self._transpile(method, kwargs)
        kwargs.pop("class")

        self.down()
        self.echo('};')
        self.classes[node.class_name] = node

    def transpile_AssignmentNode(self, node, kwargs):
        value = self._transpile(node.value, kwargs)
        type_ = self.transpile_type(node.var_type)
        if isinstance(node.value, ListNode):
            type_ = self.transpile_type(
                t_list(node.value.inferred_type)
            )
        name = self._transpile(node.var_name, kwargs)
        if variables := kwargs.get("class_vars"):
            for var in variables:
                if name == self._transpile(var.var_name, kwargs):
                    if self.transpile_type(var.var_type) != type_ and type_ != "Value" and type_ != "auto":
                        value = f"static_cast<{type_}>({value})"
                    self.echo(f"this->{name} = {value};")
                    return
        self.variables[name] = node.var_type
        if self.transpile_type(node.value) != type_ and type_ != "Value" and type_ != "auto":
            value = f"static_cast<{type_}>({value})"
        self.echo(f"{type_} {name} = {value};")

    def transpile_FunctionDefNode(self, node, kwargs: dict):
        if node.func_name == "main":
            for stmt in node.body:
                kwargs["program"].statements.append(stmt)
            return
        virtual = "virtual " if kwargs.get("class", None) and node.template else ""
        type_ = self.transpile_type(node.return_type)
        params = self.transpile_params(node.params)
        override = ""
        if cls := kwargs.get("class", None):
            if cls.parent_class:
                parent_name = cls.parent_class

                while parent_name:
                    parent = self.classes[parent_name]

                    for method in parent.methods:
                        if method.template and method.func_name == node.func_name:
                            override = "override "
                            parent_name = None
                            break
                    else:
                        parent_name = parent.parent_class

        self.echo(f"{virtual}{type_} {node.func_name}({params}) {override}{{")
        self.up()

        kwargs.update({"func": node})
        for stmt in node.body:
            if isinstance(stmt, FunctionDefNode):
                self.transpile_lambda(stmt, kwargs)
                continue
            self._transpile_stmt(stmt, kwargs)
        kwargs.pop("func")

        self.down()
        self.echo('}')

        self.functions.append(node)

    def transpile_lambda(self, node, kwargs):
        self.echo(f"auto {node.func_name} = [&]({self.transpile_params(node.params)}) {{")
        self.up()
        for stmt in node.body:
            if isinstance(stmt, FunctionDefNode):
                self.transpile_lambda(stmt, kwargs)
                continue
            self._transpile(stmt, kwargs)
        self.down()
        self.echo('};')

    def transpile_IfNode(self, node, kwargs):
        self.echo(f"if ({self._transpile(node.condition, kwargs)}) {{")
        self.up()
        for stmt in node.body:
            self._transpile_stmt(stmt, kwargs)
        self.down()
        self.echo("}")

        for condition, body in node.elif_blocks:
            self.echo(f"else if ({self._transpile(condition, kwargs)}) {{")
            self.up()
            for stmt in body:
                self._transpile_stmt(stmt, kwargs)
            self.down()
            self.echo("}")

        if node.else_body:
            self.echo("else {")
            self.up()
            for stmt in node.else_body:
                self._transpile_stmt(stmt, kwargs)
            self.down()
            self.echo("}")

    def transpile_ReturnNode(self, node: ReturnNode, kwargs: dict):
        value = self._transpile(node.value, kwargs)
        ret = self.transpile_type(kwargs["func"].return_type)
        if self.get_type(value, kwargs) != ret and ret != "Value" and ret != "auto":
            value = f"static_cast<{ret}>({value})"
        self.echo(f"return {value};")

    def transpile_WhileNode(self, node, kwargs):
        self.echo(f"while ({self._transpile(node.condition, kwargs)}) {{")
        self.up()

        for stmt in node.body:
            self._transpile_stmt(stmt, kwargs)

        self.down()
        self.echo('}')

    def get_type(self, node, kwargs):
        if isinstance(node, VarAccessNode):
            name = node.var_name

            if name.startswith("this."):
                name = name.removeprefix("this.")

            return self.variables.get(name)

        return None

    def is_object(self, node, kwargs):
        return self.get_type(node, kwargs) in self.classes

    def transpile_MethodCallNode(self, node, kwargs):
        caller = self._transpile(node.caller, kwargs)
        args = self.transpile_args(node.args, kwargs)
        if not caller:  # caller is this, meaning transpile_VarAccessNode will return ""
            return f"{node.method_name}({args})"
        if isinstance(node.caller, ImportModuleVariableNode):
            return f"{caller}::{node.method_name}({args})"
        if t := self.get_type(node.caller, kwargs):
            if isinstance(t, (t_list, t_dict)) or t is list or t is dict:
                return f"{caller}->{node.method_name}({args})"
        return f"{caller}.{node.method_name}({args})"

    def transpile_FunctionCallNode(self, node, kwargs):
        return f"{node.func_name}({self.transpile_args(node.args, kwargs)})"

    def transpile_ModifiedAssignmentNode(self, node, kwargs):
        target = self._transpile_lvalue(node.var_name, kwargs)
        value = self._transpile(node.value, kwargs)

        if (
                node.operator == "="
                and isinstance(node.var_name, IndexAccessNode)
                and (
                    isinstance(getattr(node.var_name, "container_type", None), t_dict)
                    or isinstance(node.var_name.index_expr, StringNode)
                )
        ):
            value = self._transpile(node.value, kwargs)

        self.echo(f"{target} {node.operator} {value};")

    def transpile_NumberNode(self, node, _):
        return str(node.value)

    def transpile_StringNode(self, node, _):
        return f'"{node.value}"'

    def transpile_BooleanNode(self, node: BooleanNode, _):
        return f'{"true" if node.value else "false"}'

    def transpile_VarAccessNode(self, node, kwargs):
        var_name = node.var_name
        if kwargs.get("params", None):
            if var_name == "this": return "*this"
            var_name = var_name.split(".")
            if var_name[0] == "this":
                var_name[0] = "*this"
            return ".".join(var_name)
        if var_name == "this": return ""
        var_name = var_name.split(".")
        if var_name[0] == "this":
            var_name = var_name[1:]
        return ".".join(var_name)

    def transpile_NullNode(self, node, kwargs):
        return "nullptr"

    def transpile_ImportModuleVariableNode(self, node, _):
        var_name = node.var_name
        if var_name == "this": return ""
        var_name = var_name.split(".")
        if var_name[0] == "this":
            var_name = var_name[1:]
        return ".".join(var_name)

    def transpile_ForNode(self, node, kwargs):
        iterable = self._transpile(node.iterable, kwargs)
        self.echo(f"for (auto {node.var_name} : {iterable}) {{")
        self.up()

        for stmt in node.body:
            self._transpile_stmt(stmt, kwargs)

        self.down()
        self.echo('}')

    def transpile_RangeNode(self, node, kwargs):
        start = self._transpile(node.start, kwargs)
        end = self._transpile(node.end, kwargs)
        inclusive = "true" if node.inclusive else "false"
        return f"range({start}, {end}, {inclusive})"

    def transpile_BinOpNode(self, node, kwargs):
        left = self._transpile(node.left, kwargs)
        right = self._transpile(node.right, kwargs)
        return f"({left} {node.operator} {right})"

    def transpile_ListNode(self, node, kwargs):
        return f"std::make_shared<List>(List{{{self.transpile_args(node.items, kwargs)}}})"

    def transpile_DictNode(self, node, kwargs):
        lines = []
        for key_node, value_node in node.dict.items():
            key = self._transpile(key_node, kwargs)
            value = self._transpile(value_node, kwargs)
            lines.append(f"__d->set({key}, {value});")
        body = " ".join(lines)
        return f"[&](){{ DictPtr __d = std::make_shared<Dict>(); {body} return __d; }}()"

    def transpile_UnaryOpNode(self, node: UnaryOpNode, kwargs):
        return f"{node.operator}{self._transpile(node.operand, kwargs)}"

    def _transpile_lvalue(self, node, kwargs):
        if isinstance(node, IndexAccessNode):
            return self._transpile_index_access(node, kwargs, as_lvalue=True)
        return self._transpile(node, kwargs)

    def _transpile_index_access(self, node, kwargs, as_lvalue=False):
        base = self._transpile(node.var_name, kwargs)
        index = self._transpile(node.index_expr, kwargs)
        return f"(*{base})[{index}]"

    def transpile_IndexAccessNode(self, node, kwargs):
        return self._transpile_index_access(node, kwargs)

    def transpile_AttrAccessNode(self, node, kwargs):
        return self.getAttrName(node)

    def transpile_ImportNode(self, node: ImportNode, kwargs):
        if node.module_name in self.loaded_extensions:
            ext = self.loaded_extensions[node.module_name]
            for header in ext["headers"]:
                self.echo(f'#include "{header}"')
            return
        self.echo(compile_file(node.module_name + ".gum", accessory_file=True)[2])

    def getAttrName(self, node: AttrAccessNode):
        if isinstance(node.base, AttrAccessNode):
            base = self.getAttrName(node.base)
        else:
            base = node.base.var_name
        if base == "this":
            return f"{base}->{node.attr.var_name}"
        return f"{base}.{node.attr.var_name}"
