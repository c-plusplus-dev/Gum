import re
from .tokens import Token, Tokens

class Lexer:
    def __init__(self):
        self.TOKEN_TYPES = [
            ("COMMENT", r"#"),
            ("KEYWORD", r"\b(let|def|object|return|if|elif|else|while|for|in|import|succeeds|template)\b"),
            ("BOOLEAN", r"\b(true|false)\b"),
            ("NULL", r"\bnull\b"),
            ("IDENTIFIER", r"[a-zA-Z_][a-zA-Z0-9_]*"),
            ("STRING", r'"(?:[^"\\]|\\.)*"'),
            ("NUMBER", r"\d+(\.\d+)?\b"),
            ("OPERATOR", r"\+=|-=|\*=|/=|==|!=|<=|>=|->|=>|<|>|\+|-|\*|/|=|%"),
            ("SYMBOL", r"[():{}.,\[\]]"),
            ("WHITESPACE", r"[ \t]+"),
        ]

        self.token_regex = "|".join(f"(?P<{name}>{pattern})" for name, pattern in self.TOKEN_TYPES)
        self.tokens = []

    def lex(self, code):
        lines = code.split("\n")

        for line_number, line in enumerate(lines, start=1):
            for match in re.finditer(self.token_regex, line):
                kind = match.lastgroup
                value = match.group()
                column = match.start()

                if kind in ["WHITESPACE", "COMMENT"]:
                    if kind == "COMMENT":
                        break
                    continue

                self.tokens.append(Token(kind, value, line_number, column))

        return Tokens(self.tokens, lines=lines)
