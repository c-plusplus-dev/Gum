from .tokens import *

# Base class for all AST nodes
class ASTNode:
    def __repr__(self):
        return f"<{self.__class__.__name__}>"


# ------------------------------
# Program Node (whole file)
class ProgramNode(ASTNode):
    def __init__(self, statements):
        self.statements = statements  # List of other nodes

    def __repr__(self):
        string = "ProgramNode(statements=[\n"
        for s in self.statements:
            string += f"    {s}\n"
        return string + "]"


# ------------------------------
# Variable Assignment
class AssignmentNode(ASTNode):
    def __init__(self, var_name, value, var_type=None):
        self.var_name = var_name
        self.value = value  # Could be another node (e.g., NumberNode)
        self.var_type = var_type  # Optional (int, str, etc.)

    def __repr__(self):
        return f"AssignmentNode(var_name={self.var_name}, value={self.value}, var_type={self.var_type})"


# ------------------------------
# Modified Assignment
class ModifiedAssignmentNode(ASTNode):
    def __init__(self, var_name, operator, value):
        self.var_name = var_name
        self.operator = operator
        self.value = value

    def __repr__(self):
        return f"ModifiedAssignmentNode(var_name={self.var_name}, op={self.operator}, value={self.value})"


# ------------------------------
# Index access
class IndexAccessNode(ASTNode):
    def __init__(self, var_name, index_expr, assigning, value, inferred_type=None):
        self.index_expr = index_expr
        self.var_name = var_name
        self.assigning = assigning
        self.value = value
        self.inferred_type = inferred_type

    def __repr__(self):
        return f"IndexAccessNode(var_name={self.var_name}, index={self.index_expr}" + (f", value={self.value}" if self.assigning else "") + ")"


# ------------------------------
# Range Node
class RangeNode(ASTNode):
    def __init__(self, start, end, inclusive):
        self.start = start
        self.end = end
        self.inclusive = inclusive

    def __repr__(self):
        return f"RangeNode(start={self.start}, end={self.end}, inclusive={self.inclusive})"


# ------------------------------
# Function Definition
class FunctionDefNode(ASTNode):
    def __init__(self, func_name, params, body, return_type=None, template=False):
        self.func_name = func_name
        self.params = params  # List of tuples: [(param_name, param_type, default_value)]
        self.body = body      # List of statements
        self.return_type = return_type
        self.template = template

    def __repr__(self):
        return f"FunctionDefNode(func_name={self.func_name}, params={self.params}, return_type={self.return_type}, body={self.body}, template={self.template})"


# ------------------------------
# Function Call
class FunctionCallNode(ASTNode):
    def __init__(self, func_name, args):
        self.func_name = func_name
        self.args = args  # List of expression nodes

    def __repr__(self):
        return f"FunctionCallNode(func_name={self.func_name}, args={self.args})"


# ------------------------------
# If / Elif / Else Node
class IfNode(ASTNode):
    def __init__(self, condition, body, elif_blocks=None, else_body=None):
        self.condition = condition
        self.body = body  # List of statements
        self.elif_blocks = elif_blocks or []  # List of (condition, body)
        self.else_body = else_body  # List of statements

    def __repr__(self):
        return f"IfNode(condition={self.condition}, body={self.body}, elif_blocks={self.elif_blocks}, else_body={self.else_body})"

# Null
class NullNode(ASTNode):
    def __init__(self):
        pass
def __repr__(self):
        return f"NullNode()"

# ------------------------------
# While Loop
class WhileNode(ASTNode):
    def __init__(self, condition, body):
        self.condition = condition
        self.body = body

    def __repr__(self):
        return f"WhileNode(condition={self.condition}, body={self.body})"


# ------------------------------
# For Loop
class ForNode(ASTNode):
    def __init__(self, var_name, iterable, body):
        self.var_name = var_name
        self.iterable = iterable
        self.body = body

    def __repr__(self):
        return f"ForNode(var_name={self.var_name}, iterable={self.iterable}, body={self.body})"


# ------------------------------
# Class Declaration
class ClassNode(ASTNode):
    def __init__(self, class_name, methods, parent_class=None):
        self.class_name = class_name
        self.parent_class = parent_class
        self.methods = methods

    def __repr__(self):
        return f"ClassNode(class_name={self.class_name}, parent_class={self.parent_class}, methods={self.methods})"


# ------------------------------
# Import Node
class ImportNode(ASTNode):
    def __init__(self, module_name, import_type='default', imported_name=None):
        self.module_name = module_name
        self.import_type = import_type  # 'default', 'wildcard', 'from'
        self.imported_name = imported_name  # Specific thing to import (if 'from')

    def __repr__(self):
        return f"ImportNode(module_name={self.module_name}, import_type={self.import_type}, imported_name={self.imported_name})"

class ImportModuleVariableNode(ASTNode):
    def __init__(self, var_name):
        self.var_name = var_name

    def __repr__(self):
        return f"ImportModuleVariableNode(var_name={self.var_name})"


# ------------------------------
# Return Statement
class ReturnNode(ASTNode):
    def __init__(self, value):
        self.value = value

    def __repr__(self):
        return f"ReturnNode(value={self.value})"


# ------------------------------
# Expressions -------------------
# Literal Number (int/float)
class NumberNode(ASTNode):
    def __init__(self, value):
        self.value = value

    def __repr__(self):
        return f"NumberNode(value={self.value})"


# String
class StringNode(ASTNode):
    def __init__(self, value):
        self.value = value

    def __repr__(self):
        return f"StringNode(value={self.value})"

# Lists
class ListNode(ASTNode):
    def __init__(self, items, inferred_type=None):
        self.items = items
        self.inferred_type = inferred_type

    def __repr__(self):
        return f"ListNode(items={self.items}" + (f", {self.inferred_type}" if self.inferred_type else "") + ")"

    def __iter__(self):
        return iter(self.items)

    def __getitem__(self, item):
        return self.items[item]


# Dict
class DictNode(ASTNode):
    def __init__(self, dict_):
        self.dict = dict_

    def __repr__(self):
        return f"DictNode(dict={BeautyfiedDict(self.dict)})"

    def __iter__(self):
        return iter(self.dict)

    def __getitem__(self, item):
        return self.dict[item]


# Method
class MethodCallNode(ASTNode):
    def __init__(self, caller, method_name, args):
        self.caller = caller
        self.method_name = method_name
        self.args = args

    def __repr__(self):
        return f"MethodCallNode(caller={self.caller}, method_name={self.method_name}, args={self.args})"


# Boolean
class BooleanNode(ASTNode):
    def __init__(self, value):
        self.value = value  # True / False

    def __repr__(self):
        return f"BooleanNode(value={self.value})"


# Variable Reference
class VarAccessNode(ASTNode):
    def __init__(self, var_name):
        self.var_name = var_name

    def __repr__(self):
        return f"VarAccessNode(var_name={self.var_name})"


# Attribute Access
class AttrAccessNode(ASTNode):
    def __init__(self, base, attr):
        self.base = base
        self.attr = attr

    def __repr__(self):
        return f"AttrAccessNode(base={self.base}, attr={self.attr})"


# Binary Operation
class BinOpNode(ASTNode):
    def __init__(self, left, operator, right):
        self.left = left    # Left node
        self.operator = operator  # String, e.g., '+'
        self.right = right  # Right node

    def __repr__(self):
        return f"BinOpNode(left={self.left}, operator={self.operator}, right={self.right})"


# Unary Operation
class UnaryOpNode(ASTNode):
    def __init__(self, operator, operand):
        self.operator = operator
        self.operand = operand

    def __repr__(self):
        return f"UnaryOpNode(operator={self.operator}, operand={self.operand})"
