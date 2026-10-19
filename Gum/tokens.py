class Tokens:
    def __init__(self, tokens, file=None, lines=None):
        self.tokens = tokens
        self.file = file
        self.lines = lines

    def __iter__(self):
        yield from self.tokens

    def __getitem__(self, item: int):
        return self.tokens[item]

    def __len__(self):
        return len(self.tokens)

    def __str__(self):
        string = "Tokens: [\n"
        delimiter = " " * 4
        for token in self.tokens:
            string += delimiter + str(token) + ','
            string += "\n"
        string = string[:-2] + "\n]"
        return string


class Token:
    def __init__(self, type, value, line=None, col=0):
        self.type = type
        self.value = value
        self.line = line
        self.col = col

    def __str__(self):
        return f"({self.type}, {self.value}, {self.line}, {self.col})"

    def __iter__(self):
        yield self.type
        yield self.value
        yield self.line
        yield self.col

    def __getitem__(self, item: int):
        return list(iter(self))[item]

    def __repr__(self):
        return f"({self.type}, {self.value}, {self.line})"

class BeautyfiedList(list):
    def __init__(self, seq=None, indent_level=0):
        super().__init__(seq or [])
        self.indent_level = indent_level

    def __str__(self):
        string = "[\n"
        for value in self:
            if isinstance(value, dict):
                value = BeautyfiedDict(seq=value, indent_level=self.indent_level + 4)
                value_str = str(value)
            elif isinstance(value, list):
                value = BeautyfiedList(seq=value, indent_level=self.indent_level + 4)
                value_str = str(value)
            else:
                value_str = repr(value)
            string += " " * self.indent_level + f"    {value_str}\n"
        string += " " * self.indent_level + "]"
        return string

class BeautyfiedDict(dict):
    def __init__(self, seq=None, indent_level=0, visited=None, **kwargs):
        super().__init__(seq or {}, **kwargs)
        self.indent_level = indent_level
        self.visited = visited if visited is not None else set()

    def __str__(self):
        self.visited.add(id(self))
        string = "{\n"
        for key, value in self.items():
            if isinstance(value, dict):
                if id(value) in self.visited:
                    value_str = "<Circular Reference>"
                else:
                    value = BeautyfiedDict(seq=value, indent_level=self.indent_level + 4, visited=self.visited)
                    value_str = str(value)
            elif isinstance(value, list):
                value = BeautyfiedList(seq=value, indent_level=self.indent_level + 4)
                value_str = str(value)
            else:
                value_str = repr(value)
            string += " " * self.indent_level + f"    {key}: {value_str}\n"
        string += " " * self.indent_level + "}"
        return string
