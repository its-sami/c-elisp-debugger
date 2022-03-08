import gdb
from enum import Enum, auto

class FrameType(Enum):
    ARG = auto()
    BODY = auto()
    BREAKPOINT = auto()
    UNKNOWN = auto()


class FrameState(Enum):
    ENTRY = auto()
    ARG = auto()
    BODY = auto()
    END = auto()
    UNKNOWN = auto()


class NavCommand(Enum):
    # NOTE: keep the ordering here
    # use it for later
    # but lower value means lower on the "stop hierarchy"
    # i.e. will stop for more
    STEP = 1
    NEXT = 2
    UP = 3


class Frame:
    def __init__(self, manager, frame_type, start, breakpoint=None):
        self.manager = manager
        self.type = frame_type
        self.breakpoint = breakpoint
        self.command = NavCommand.STEP

        self.frame = gdb.newest_frame()
        if self.type == FrameType.UNKNOWN:
            self.state = FrameState.UNKNOWN
        else:
            self.state = FrameState.ENTRY

        self.start = start
        # START is a breakpoint to enter the function
        # if it is None then we must already be in the function we care about
        if self.start:
            self.finish = None
        else:
            self.finish = gdb.FinishBreakpoint(internal=True)

        self.args = set()
        self.bodies = set()
        self.disabled = set()

    def hit(self, bp):
        assert self.cares_about(bp)

        if bp == self.start:
            self.do_start(bp)
            return

        assert(self.start is None) # just being defensive

        step_in = bp in self.looking_for()

        if bp in self.args:
            self.do_arg(bp, step_in)
        elif bp in self.bodies:
            self.do_body(bp, step_in)
        elif bp == self.finish:
            self.do_finish(bp)

        if step_in:
            print("*** BACKTRACE ***")
            print(self.manager.frame_list(backtrace=True))
            print()
        else:
            gdb.execute("continue")

    def cares_about(self, bp):
        return bp in self.enabled or bp == self.finish or bp == self.start

    def looking_for(self):
        important_bps = set()

        if self.command.value <= NavCommand.UP.value:
            important_bps |= {self.finish}


        if self.command.value <= NavCommand.NEXT.value:
            important_bps |= self.bodies

        if self.command.value <= NavCommand.STEP.value:
            important_bps |= self.args

        return important_bps

    def step(self):
        self.command = NavCommand.STEP
        gdb.execute("continue")

    def next(self):
        self.command = NavCommand.NEXT
        gdb.execute("continue")

    def up(self):
        self.command = NavCommand.UP
        gdb.execute("continue")

    def cont(self):
        self.up()

    @property
    def enabled(self):
        return (self.args | self.bodies) - self.disabled

    def enable(self):
        for bp in self.disabled:
            bp.enabled = True

        self.disabled = set()

    def disable(self, *bps):
        for bp in bps:
            bp.enabled = False
            self.disabled.add(bp)

    def setup(self):
        pass

    def do_start(self, bp):
        print("=== start ===")
        self.start = None
        self.finish = gdb.FinishBreakpoint(internal=True)
        self.enable()

        self.setup()

    def do_arg(self, bp, step_in):
        raise NotImplementedError()

    def do_body(self, bp, step_in):
        raise NotImplementedError()

    def do_finish(self, bp):
        print("=== finish ===")
        ret = LispObject.create(bp.return_value)
        print(f"evaluation: {ret}")

        self.cleanup()

    def cleanup(self):
        for arg in self.args:
            if arg.is_valid():
                arg.delete()

        for body in self.bodies:
            if body.is_valid():
                body.delete()

        if self.finish.is_valid():
            self.finish.delete()

        self.manager.pop()

    def step_in(self, subframe):
        self.disable(*self.enabled)
        self.manager.push(subframe)

    def get_response(self, msg="step in?"):
        return input("{msg} [yN] ") == "y"

    def __str__(self):
        return f"{self.type.name} @{self.state.name}"

    @staticmethod
    def frame_wrapper(function):
        if function == CFunctions.EVAL_SUB:
            return EvalFrame
        elif function == CFunctions.FUNCALL_LAMBDA:
            return LambdaFrame
        elif function == CFunctions.FUNCALL_SUBR:
            return SubrFrame

class EvalFrame(Frame):
    def __init__(self, manager, frame_type, start, breakpoint=None):
        super().__init__(manager, frame_type, start, breakpoint=breakpoint)

        self.args = { gdb.Breakpoint(label, internal=True) for label in [
            "eval_sub:func_subr_arg_many",
            "eval_sub:func_subr_arg_n",
            "apply_lambda:func_lambda_args",
        ] }

        self.bodies = { gdb.Breakpoint(label, internal=True) for label in [
            "eval_sub:func_subr_body_many",
            "eval_sub:func_subr_body_n",
            "eval_sub:func_subr_body_unevalled",
            "Fprogn:func_lambda_body",
        ] }

        if self.start:
            self.disable(*self.enabled)
            self.fun = None
        else:
            self.setup()

        self.expr_type = None

    def setup(self):
        self.fun = LispFunction.create()
        print(f"FUNCTION: {self.fun}")

    def __str__(self):
        return f"[{self.fun.name() if self.fun else '-'}] : {super().__str__()}"

    def do_arg(self, bp, step_in):
        self.set_expr_type(bp.location)

        #remove irrelevant breakpoints
        if self.state == FrameState.ENTRY:
            to_remove = self.args - {bp}
            self.args -= to_remove

            for arg in to_remove:
                arg.delete()

            to_remove = self.bodies - self.get_body(bp)
            self.bodies -= to_remove

            for body in to_remove:
                body.delete()

        if not step_in:
            print("stepping through arg")
            return

        print("=== arg ===")
        print("start point...")
        sub_start = gdb.Breakpoint("eval_sub", internal=True, temporary=True)

        #always an eval I think...
        subframe = EvalFrame(self.manager, FrameType.ARG, sub_start)
        self.step_in(subframe)

    def do_body(self, bp, step_in):
        self.set_expr_type(bp.location)

        #can't go back to arguments from a body
        for arg in self.args:
            arg.delete()
            self.args = set()


        if not step_in:
            print("stepping over")
            return

        print("=== body ===")


        #need to construct the next frame
        if self.expr_type == ExprType.CONS:
            print("start point...")
            sub_start = gdb.Breakpoint("eval_sub", internal=True, temporary=True)
            subframe = EvalFrame(self.manager, FrameType.BODY, sub_start)
        elif self.expr_type == ExprType.SUBR:
            fun = gdb.newest_frame().read_var("fun")
            subr = LispObject.create(fun)

            print("start point...")
            func_addr = f"*{LispObject.raw_object(subr.function())}"
            sub_start = gdb.Breakpoint(func_addr, internal=True, temporary=True)
            subframe = PrimitiveFrame(self.manager, subr, sub_start)

        self.step_in(subframe)

    def set_expr_type(self, label):
        if self.expr_type is None:
            self.expr_type = ExprType.get_type(label)
            print(f"setting {self} type to {self.expr_type.name}")
        else:
            print(f"{self} type is {self.expr_type.name}")

    def get_body(self, arg):
        pairings = {
            "eval_sub:func_subr_arg_many": "eval_sub:func_subr_body_many",
            "eval_sub:func_subr_arg_n": "eval_sub:func_subr_body_n",
            "apply_lambda:func_lambda_args": "Fprogn:func_lambda_body"
        }

        loc = pairings.get(arg.location)

        res = {body for body in self.bodies if body.location == loc}

        assert(len(res) < 2)
        return res


class PrimitiveFrame(Frame):
    def __init__(self, manager, subr, start):
        self.subr = subr
        print(f"PRIMITIVE: {self.subr}")

        super().__init__(manager, FrameType.BODY, start) #always in a body

        # print("IGNORE"*3)
        self.bodies = { gdb.Breakpoint(func.value, internal=True)
                        for func in CFunctions }
        # print("STOP IGNORING")

        if self.start:
            self.disable(*self.enabled)
            self.guts = False
        else:
            self.setup()

    def setup(self):
        resp = input("debug primitive as C? [y/N] > ").strip().lower()

        if resp == "y":
            self.guts = True
            self.disable(*self.enabled)

    def do_body(self, bp, step_in):
        if not step_in:
            print("stepping over")
            return

        print("== body ==")

        subframe_class = self.frame_wrapper(CFunctions(bp.location))
        subframe = subframe_class(self.manager, FrameType.BODY, None)

        self.step_in(subframe)

    def cont(self):
        if self.guts:
            self.enable()
            self.command = NavCommand.STEP
            gdb.execute("continue")
        else:
            super().cont()

    def __str__(self):
        return f"[{self.subr}] : {super().__str__()}"


class LambdaFrame(Frame):
    def __init__(self, manager, frame_type, start, breakpoint=None):
        super().__init__(manager, frame_type, start, breakpoint=breakpoint)

        self.bodies = { gdb.Breakpoint("eval_sub", internal=False) }

        if start:
            self.disable(*self.enabled)
        else:
            self.setup()

    def setup(self):
        self.fun = LispFunction.create()

    def do_start(self, bp):
        self.setup()
        super().do_start(bp)

    def do_body(self, bp, step_in):
        if not step_in:
            print("stepping over")
            return

        print("== body ==")
        subframe = EvalFrame(self.manager, FrameType.BODY, None)

        self.step_in(subframe)

    def __str__(self):
        return f"[{self.fun.name() if self.fun else '-'}] : {super().__str__()}"


class SubrFrame(Frame):
    def __init__(self, manager, frame_type, start, breakpoint=None):
        super().__init__(manager, frame_type, start, breakpoint=breakpoint)

        if start:
            self.disable(*self.enabled)

            self.subr = None
            self.bodies = set()
        else:
            self.setup()

    def setup(self):
        self.subr = LispFunction.create()
        subr = self.subr.subr

        func_addr = f"*{LispObject.raw_object(subr.function())}"
        self.bodies = { gdb.Breakpoint(func_addr, internal=False) }

    def do_start(self, bp):
        self.setup()
        super().do_start(bp)

    def do_body(self, bp, step_in):
        if not step_in:
            print("stepping over")
            return

        print("== body ==")
        subframe = PrimitiveFrame(self.manager, self.subr, None)

        self.step_in(subframe)

    def __str__(self):
        return f"[{self.subr.name() if self.subr else '-'}] : {super().__str__()}"


class ExprType(Enum):
    SUBR = PrimitiveFrame
    CONS = EvalFrame

    @staticmethod
    def get_type(label):
        if label in { "eval_sub:func_subr_arg_many",
                      "eval_sub:func_subr_arg_n",
                      "eval_sub:func_subr_body_many",
                      "eval_sub:func_subr_body_n",
                      "eval_sub:func_subr_body_unevalled", }:
            return ExprType.SUBR
        elif label in { "Fprogn:func_lambda_body",
                        "apply_lambda:func_lambda_args", }:
            return ExprType.CONS
