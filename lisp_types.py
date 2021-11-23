import gdb
from typing import List, Optional, Union, Generator

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
            LispCons,
            LispFloat,
            LispString,
            LispVector,
            LispSubr,
        ]

        is_tagged = LispObject.is_tagged(obj)
        for lisp_type in valid_types:
            if lisp_type.claims(obj, is_tagged):
                return lisp_type(obj, is_tagged)


        #vectorlike is a weird edge case
        if is_tagged and LispVectorlike.claims(obj, is_tagged):
            return LispVectorlike(obj, is_tagged)
        else:
            print("i dunno what this is :(")

            if is_tagged:
                print(gdb.parse_and_eval(f"XTYPE({obj})"))
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

    def contents(self):
        if self.nilp():
            return []
        raise NotImplementedError("haven't made contents for general symbols yet")

    def name(self):
        if self.tagged:
            raw_str = gdb.parse_and_eval(f"SYMBOL_NAME({self.object})")
        else:
            raw_str = self.object.dereference()["u"]["s"]["name"]

        #return LispString(raw_str, True)
        return raw_str

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
            return obj.type == gdb.lookup_type("EMACS_INT")

    def untagged_str(self) -> str:
        pass

class LispCons(LispObject):
    type_code = "Lisp_Cons"
    type_untagger = "XCONS"
    type_pred = "CONSP"
    lisp_type = gdb.lookup_type("struct Lisp_Cons").pointer()

    def car(self) -> LispObject:
        if self.tagged:
            car = gdb.parse_and_eval(f"XCAR({self.object})")
        else:
            car = self.object.dereference()["car"]

        return LispObject.create(car)

    def cdr(self) -> LispObject:
        if self.tagged:
            cdr = gdb.parse_and_eval(f"XCDR({self.object})")
        else:
            cdr = self.object.dereference()["cdr"]

        return LispObject.create(cdr)

    def contents(self) -> Generator[LispObject, None, None]:
        remaining = self
        while not remaining.nilp():
            yield remaining.car()
            remaining = remaining.cdr()

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

#vectorlike encodes a bunch of different types in the source
#extract these out and make them inherit from LispObject as needed
class LispVectorlike(LispObject):
    type_code = "Lisp_Vectorlike"
    type_pred = "VECTORLIKEP"

    def __init__(self, obj: gdb.Value, tagged: bool):
        assert tagged
        super().__init__(obj, tagged)


#necessary vectorlikes
class LispVector(LispObject):
    type_code = LispVectorlike.type_code
    type_untagger = "XVECTOR"
    type_pred = "VECTORP"
    lisp_type = gdb.lookup_type("struct Lisp_Vector").pointer()

    def untagged_str(self) -> str:
        raise NotImplementedError()


class LispSubr(LispObject):
    type_code = LispVectorlike.type_code
    type_untagger = "XSUBR"
    type_pred = "SUBRP"
    lisp_type = gdb.lookup_type("struct Lisp_Subr").pointer()

    UNEVALLED = gdb.parse_and_eval("UNEVALLED")
    MANY = gdb.parse_and_eval("MANY")

    def num_args(self) -> Union[range, str]:
        subr = self.untag().dereference()

        max_args = subr["max_args"]
        if max_args == self.UNEVALLED:
            return self.UNEVALLED
        elif max_args == self.MANY:
            return self.MANY

        min_args = subr["min_args"]
        return range(min_args, max_args)

    def name(self) -> str:
        return self.object.dereference()["symbol_name"].string()

    def untagged_str(self) -> str:
        return self.name()
