class t_function:
    def __init__(self, parameters, ret):
        self.parameters = parameters
        self.ret = ret

class t_any: pass

class t_list:
    def __init__(self, item_type):
        self.item_type = item_type

    def __eq__(self, other):
        return (
            isinstance(other, t_list)
            and self.item_type == other.item_type
        )

    def __repr__(self):
        return f"list[{self.item_type!r}]"


class t_dict:
    def __init__(
        self,
        key_type=t_any,
        value_type=t_any,
        fields=None,
    ):
        self.key_type = key_type
        self.value_type = value_type

        # Known literal keys:
        #
        # {
        #     "path": str,
        #     "width": int,
        # }
        self.fields = fields or {}

    def field_type(self, key):
        return self.fields.get(key, self.value_type)

    def __eq__(self, other):
        return (
            isinstance(other, t_dict)
            and self.key_type == other.key_type
            and self.value_type == other.value_type
            and self.fields == other.fields
        )

    def __repr__(self):
        return (
            f"dict[{self.key_type!r}, {self.value_type!r}, "
            f"fields={self.fields!r}]"
        )
