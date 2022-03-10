import gdb

class VariableLookup:
    @staticmethod
    def stringify(contents):
        return gdb.parse_and_eval(f'make_multibyte_string("{contents}", {len(contents)}, (sizeof "{contents}") - 1)')

    @staticmethod
    def lookup(sym_name, obarray):
        name = VariableLookup.stringify(sym_name)
        obj = gdb.parse_and_eval(f"oblookup({obarray}, SSDATA({name}), SCHARS({name}), SBYTES({name}))")

        symbol = LispObject.create(obj)
        if isinstance(symbol, LispSymbol):
            return symbol

    @staticmethod
    def get_val(sym_name, obarray="globals.f_Vobarray"):
        symbol = VariableLookup.lookup(sym_name, obarray)

        if symbol is None:
            return None

        obj = gdb.parse_and_eval(f"find_symbol_value({symbol.object_address})")
        return LispObject.create(obj)
