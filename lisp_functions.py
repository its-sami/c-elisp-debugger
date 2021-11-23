import gdb
from typing import List, Optional, Union
from enum import Enum

class LispFunction:
    def __init__(self, frame: gdb.Frame):
        self.frame = frame

    def name(self) -> str:
        raise NotImplementedError()

    def args_list(self) -> list[LispObject]:
        raise NotImplementedError()

    @staticmethod
    def create(frame: Optional[gdb.Frame] = None):
        if frame is None:
            frame = gdb.selected_frame()

        if CFunctions.cool_func(frame.name()):
            c_func = CFunctions(frame.name())
            return c_func.wrapper()(frame)
        else:
            raise InvalidFunctionCall(frame.name())

    @staticmethod
    def breakpoint(func_name: str):
        pass


class LispArg:
    def __init__(self, symbol, value):
        self.sym = symbol
        self.val = value

    def value(self):
        return gdb.Value(str(self.val))

    def symbol(self):
        return str(self.sym)


class Eval(LispFunction):
    def __init__(self, frame: gdb.Frame):
        super().__init__(frame)

        self.form = LispObject.from_var("form", frame=frame)

    def name(self) -> str:
        if isinstance(self.form, LispCons):
            return str(self.form.car())
        else:
            return str(self.form)

    def args_list(self):
        if isinstance(self.form, LispCons):
            yield from (LispArg(str(i), arg) for i, arg in enumerate(self.form.cdr().contents()))

    def __str__(self) -> str:
        return str(self.form)


class Lambda(LispFunction):
    def __init__(self, frame: gdb.Frame):
        super().__init__(frame)

        self.fun = LispObject.from_var("fun", frame=frame)
        self.args = frame.read_var("arg_vector")
        self.numargs = frame.read_var("nargs")

    def name(self) -> str:
        if gdb.parse_and_eval(f"COMPILEDP ({self.fun.object})"):
            return "**compiled**"
        else:
            return "**lambda**"

    def args_list(self) -> list:
        try:
            args_typ = self.args.type.target().array(self.numargs)
            args_arr = self.args.dereference().cast(args_typ)


            args =  [LispArg(i, LispObject.create(args_arr[i]))
                     for i in range(self.numargs)]
            return args
        except gdb.MemoryError:
            trash_args = [LispArg(i, "???") for i in range(self.numargs)]
            raise InvalidArgsError(self.frame, trash_args)

    def __str__(self) -> str:
        return f"{self.name()} ({self.numargs}) {[(arg.symbol(), arg.value()) for arg in self.args_list()]}"


class Subr(LispFunction):
    def __init__(self, frame: gdb.Frame):
        super().__init__(frame)


        self.subr = LispObject.from_var("subr", frame)
        self.numargs = frame.read_var("numargs")
        self.args = frame.read_var("args")

    def name(self) -> str:
        return self.subr.name()

    def args_list(self) -> list:
        args_typ = self.args.type.target().array(self.numargs)
        args_arr = self.args.dereference().cast(args_typ)

        return [LispArg(i, LispObject.create(args_arr[i]))
                for i in range(self.numargs)]

    def __str__(self) -> str:
        return f"{self.name()} ({self.numargs}) {[(arg.symbol(), arg.value()) for arg in self.args_list()]}"


class CFunctions(Enum):
    EVAL_SUB = "eval_sub"
    FUNCALL_LAMBDA = "funcall_lambda"
    FUNCALL_SUBR = "funcall_subr"

    def wrapper(self) -> type[LispFunction]:
        if self == CFunctions.EVAL_SUB:
            return Eval
        elif self == CFunctions.FUNCALL_LAMBDA:
            return Lambda
        elif self == CFunctions.FUNCALL_SUBR:
            return Subr
        else:
            raise Exception("missing enum case")

    @staticmethod
    def cool_func(func_name) -> bool:
        return func_name in {func.value for func in CFunctions}


#MARK: exceptions
class InvalidFunctionCall(Exception):
    def __init__(self, func_name: str):
        super().__init__(f"function '{func_name}' is not a valid entry point to a Lisp")


class InvalidArgsError(Exception):
    def __init__(self, frame: gdb.Frame, args: list):
        super().__init__(f"could not extract args from frame: {frame}")
        self.args = args
