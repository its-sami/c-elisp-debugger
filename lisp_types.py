import gdb
from typing import List, Optional

class LispObject:
    def __init__(self, obj: gdb.Value, tagged: bool):
        assert self.claims(obj, tagged)
        self.object = obj
        self.tagged = tagged

    def nilp(self) -> bool:
        if self.tagged:
            return gdb.parse_and_eval(f"NILP({self.object})")
        else:
            return gdb.parse_and_eval(f"*{self.object} == Qnil")

    def tagging_allowed(self) -> bool:
        if self.tagged:
            return True
        else:
            ptr_as_int = gdb.parse_and_eval(f"XLI(XPL({self.object}))")
            return gdb.parse_and_eval(f"FIXNUM_OVERFLOW_P({ptr_as_int})")


    def tag_untagged(self) -> gdb.Value:
        assert not self.tagged
        return gdb.parse_and_eval(f"make_lisp_ptr({self.object}, {self.type_code})")

    def tag(self):
        assert self.tagging_allowed()
        obj = self.object if self.tagged else self.tag_untagged()

        return self.__class__(obj, True)

    def untag_tagged(self) -> gdb.Value:
        assert self.tagged
        return gdb.parse_and_eval(f"{self.type_untagger} ({self.object})")

    def untag(self):
        obj = self.untag_tagged() if self.tagged else self.object
        return self.__class__(obj, False)

    def __eq__(self, other) -> bool:
        assert isinstance(other, LispObject)

        return self.untag().object == other.untag().object

    def untagged_str(self) -> str:
        raise NotImplementedError()

    def __str__(self) -> str:
        if self.tagged:
            # need to free this string somewhere
            return gdb.parse_and_eval(f'debug_format("%s", {self.object})').string()
        else:
            return self.untagged_str()

    @staticmethod
    def is_tagged(obj: gdb.Value) -> bool:
        return obj.type == gdb.lookup_type("Lisp_Object")

    @classmethod
    def claims(cls, obj: gdb.Value, tagged: bool) -> bool:
        if tagged:
            return gdb.parse_and_eval(f"{cls.type_pred} ({obj})")
        else:
            return obj.type == cls.lisp_type

    @staticmethod
    def create(obj: gdb.Value):
        valid_types = [
            LispSymbol,
            LispInteger,
            LispVector,
            LispCons,
            LispFloat,
            LispString,
            LispSubr,
        ]

        is_tagged = LispObject.is_tagged(obj)
        for lisp_type in valid_types:
            if lisp_type.claims(obj, is_tagged):
                return lisp_type(obj, is_tagged)

        print("i dunno what this is :(")
        if is_tagged:
            print(gdb.parse_and_eval("XTYPE({obj})"))
        else:
            print(obj.type)

    @staticmethod
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

class LispSymbol(LispObject):
    type_code = "Lisp_Symbol"
    type_untagger = "XSYMBOL"
    type_pred = "SYMBOLP"
    lisp_type = gdb.lookup_type("struct Lisp_Symbol").pointer()

    def untagged_str(self) -> str:
        pass

class LispInteger(LispObject):
    type_untagger = "XFIXNUM"
    type_pred = "FIXNUMP"

    def tag_untagged(self) -> gdb.Value:
        raise NotImplementedError()

    @classmethod
    def claims(cls, obj: gdb.Value, tagged: bool) -> bool:
        if tagged:
            return gdb.parse_and_eval(f"FIXNUMP({obj})")
        else:
            return obj.type == gdb.lookup_type("struct Lisp_Int0").pointer() \
                or obj.type == gdb.lookup_type("struct Lisp_Int1").pointer()

    def untagged_str(self) -> str:
        pass

class LispVector(LispObject):
    type_code = "Lisp_Vectorlike"
    type_untagger = "XVECTOR"
    type_pred = "VECTORP"
    lisp_type = gdb.lookup_type("struct Lisp_Vector").pointer()

    def untagged_str(self) -> str:
        pass

class LispCons(LispObject):
    type_code = "Lisp_Cons"
    type_untagger = "XCONS"
    type_pred = "CONSP"
    lisp_type = gdb.lookup_type("struct Lisp_Cons").pointer()

    def untagged_str(self) -> str:
        pass

class LispFloat(LispObject):
    type_code = "Lisp_Float"
    type_untagger = "XFLOAT"
    type_pred = "FLOATP"
    lisp_type = gdb.lookup_type("struct Lisp_Float").pointer()

    def untagged_str(self) -> str:
        pass

class LispString(LispObject):
    type_code = "Lisp_String"
    type_untagger = "XSTRING"
    type_pred = "STRINGP"
    lisp_type = gdb.lookup_type("struct Lisp_String").pointer()

    def untagged_str(self) -> str:
        pass

class LispSubr(LispObject):
    type_code = "Lisp_Vectorlike"
    type_untagger = "XSUBR"
    type_pred = "SUBRP"
    lisp_type = gdb.lookup_type("struct Lisp_Subr").pointer()

    def untagged_str(self) -> str:
        pass
