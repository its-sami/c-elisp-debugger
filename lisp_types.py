import gdb
from typing import List, Optional

def nilp(obj):
    return gdb.parse_and_eval(f"NILP({obj.object})")

class LispObject:
    def __init__(self, obj: gdb.Value):
        assert self.correct_type(obj)
        self.object = obj

    def correct_type(self, obj: gdb.Value):
        # N.B. LispObject does not have a "type_name"
        # so don't call LispObject(obj) directly
        # use LispObject.create(obj) instead
        return gdb.parse_and_eval(f"{self.type_name}P({obj})")

    def create(obj: gdb.Value):
        if gdb.parse_and_eval(f"SYMBOLP({obj})"):
            return LispSymbol(obj)
        elif gdb.parse_and_eval(f"FIXNUMP({obj})"):
            return LispInteger(obj)
        elif gdb.parse_and_eval(f"VECTORLIKEP({obj})"):
            return LispVector(obj)
        elif gdb.parse_and_eval(f"CONSP({obj})"):
            return LispCons(obj)
        elif gdb.parse_and_eval(f"FLOATP({obj})"):
            return LispFloat(obj)
        elif gdb.parse_and_eval(f"STRINGP({obj})"):
            return LispString(obj)
        else:
            print("i dunno what this is :(")
            print(gdb.parse_and_eval("XTYPE({obj})"))

    def from_var(name: str, frame: Optional[gdb.Frame] = None):
        if frame is not None:
            return LispObject.create(frame.read_var(name))

        obj, _ = gdb.lookup_symbol(name)

        if obj is None:
            # using value error to match behaviour of frame.read_var
            raise ValueError(f"Variable '{name}' not found")

        if obj.needs_frame:
            return LispObject.create(obj.value(gdb.selected_frame()))
        else:
            return LispObject.create(obj.value())

    def __eq__(self, other) -> bool:
        assert isinstance(other, LispObject)
        return gdb.parse_and_eval(f"EQ({self.object}, {other.object})")

    def __str__(self) -> str:
        desc_str = gdb.parse_and_eval(f'debug_format("%s", {self.object})')
        #free the string somehow
        return desc_str.string()


class LispSymbol(LispObject):
    type_name = "SYMBOL"

    def name(self):
        s = LispString(gdb.parse_and_eval(f"XSYMBOL({self.object})->u.s.name"))
        return s.contents()

    def value(self):
        return gdb.parse_and_eval(f"Findirect_variable({self.object})")

    def function(self):
        return gdb.parse_and_eval(f"XSYMBOL({self.object})->u.s.function")


class LispInteger(LispObject):
    type_name = "INTEGER"

    def value(self):
        return gdb.parse_and_eval(f"XFIXNUM({obj})")


class LispVector(LispObject):
    type_name = "VECTOR"

    def correct_type(self, obj: gdb.Value):
        return gdb.parse_and_eval(f"VECTORLIKEP({obj})")


class LispCons(LispObject):
    type_name = "CONS"

    def car(self) -> LispObject:
        car = gdb.parse_and_eval(f"XCAR({self.object})")
        return LispObject.create(car)

    def cdr(self) -> LispObject:
        cdr = gdb.parse_and_eval(f"XCDR({self.object})")
        return LispObject.create(cdr)

    def is_nil(self) -> bool:
        return gdb.parse_and_eval(f"NILP({self.object})")

    def contents(self):
        rest = self.object

        while not rest.is_nil():
            yield rest.car()
            rest = rest.cdr()


class LispFloat(LispObject):
    type_name = "FLOAT"

    def value(self):
        return gdb.parse_and_eval(f"XFLOAT_DATA({self.object})")


class LispString(LispObject):
    type_name = "STRING"

    def contents(self):
        return gdb.parse_and_eval(f"SSDATA({self.object})")


class LispSubr(LispObject):
    type_name = "SUBR"
