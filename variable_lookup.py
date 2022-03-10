import gdb

class VariableLookup:
    @staticmethod
    def stringify(contents):
        return gdb.parse_and_eval(f'make_multibyte_string("{contents}", {len(contents)}, (sizeof "{contents}") - 1)')

    @staticmethod
    def lookup(sym_name, obarray):
        name = VariableLookup.stringify(sym_name)
        return gdb.parse_and_eval(f"oblookup({obarray}, SSDATA({name}), SCHARS({name}), SBYTES({name}))")

    @staticmethod
    def get_val(sym_name, obarray="globals.f_Vobarray"):
        symbol = VariableLookup.lookup(sym_name, obarray)
        print(LispObject.create(symbol))
        obj = gdb.parse_and_eval(f"find_symbol_value({symbol})")

        return LispObject.create(obj)
