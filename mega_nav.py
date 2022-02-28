import gdb
from enum import Enum, auto

class Manager:
    def __init__(self):
        self.name = "MAIN"
        self.breakpoints = []
        self.disabled = set()

        self.recovery = None

        self.frames = []

        self.breakpoint()
        gdb.events.stop.connect(self.hit)

    #TODO: maybe need to make this the only listener?
    # could subclass internal breakpoints, and pass around frames
    # ALL THIS TO AVOID doubling up on breakpoints
    # i.e. user wants to debug an argument
    # but that's a function they've breakpointed
    def hit(self, event):
        if not isinstance(event, gdb.BreakpointEvent):
            return

        print("*** BACKTRACE ***")
        print(self.frame_list())
        print()

        events = {
            EventType.USER_BP: [],
            EventType.INNER_BP: [],
            EventType.RECOVERY_BP: []
        }

        for bp in event.breakpoints:
            if bp in self.breakpoints:
                events[EventType.USER_BP].append(bp)

            if bp == self.recovery:
                events[EventType.RECOVERY_BP].append(bp)

            events[EventType.INNER_BP] = [ (bp, frame)
                                           for frame in reversed(self.frames)
                                           if frame.cares_about(bp) ]

        '''
        print("CHECKING FOR A HIT")
        print(events)
        if events[EventType.RECOVERY_BP]:
            print("recovery")
        if events[EventType.USER_BP]:
            print("user")
        if events[EventType.INNER_BP]:
            print("inner")

        for event_type, bps in events.items():
            if bps:
                print(event_type.name)
        '''

        # need to figure out priorities of breakpoints
        if bps := events[EventType.RECOVERY_BP]:
            print("wow we made it :)")
            frame = EvalFrame(self, FrameType.UNKNOWN, None)
            self.push(frame)
        elif bps := events[EventType.USER_BP]:
            bp = bps[0] #TODO: can i just use the first one?
            print("ding ding ding")
            print(bp)
            # print("MAKING A BREAKPOINT!!!\n\n")

            #FIXME: disabling breakpoint when entering debug for that bp
            # for some reason they're triggering on other frames?
            #FIX: I THINK the breakpoint only checks if its in the function
            # i.e. any breakpoint within a function counts
            # not just when it enters the function?
            self.disable(bp)

            #already in this frame so no need to insert a START point
            frame = EvalFrame(self, FrameType.BREAKPOINT, None, breakpoint=bp)

            # print(f"[{self}] {bp.location}")
            self.push(frame)
        elif events[EventType.INNER_BP]:
            #take first one -- this will be the most recent frame which wants it
            bp, frame = events[EventType.INNER_BP][0]

            frame.hit(bp)

    def breakpoint(self):
        eval, subr = LispBreakpoint.create("sami/arg")

        self.breakpoints.append(eval)
        self.breakpoints.append(subr)

    def disable(self, breakpoint):
        breakpoint.enabled = False
        self.disabled.add(breakpoint)

    def enable(self, breakpoint=None):
        if breakpoint is not None:
            assert (breakpoint in self.disabled)
            breakpoint.enabled = True
            self.disabled.remove(breakpoint)
            return

        for bp in self.disabled:
            bp.enabled = True

        self.disabled = set()

    def push(self, frame):
        # print(f"pushing {frame}")
        self.frames.append(frame)

    def pop(self):
        return self.frames.pop()

    def head(self):
        return self.frames[-1]

    def full(self):
        return len(self.frames) > 0

    def empty(self):
        return len(self.frames) == 0

    def rebuild(self):
        def find_prev_frame(frame):
            '''
            Find the previous *RELEVANT* frame on the real stack
            '''
            print("lets run it back")
            while frame.older():
                frame = frame.older()

                if CFunctions.cool_func(frame.name()):
                    return frame

        if (prev := find_prev_frame(gdb.newest_frame())) is None:
            print("no more frames to use")
            return

        if self.full() and self.head().frame == prev:
            print("everything already cool")
            return

        if (one_before := prev.newer()) is None:
            print("weird case... make sure you've popped before calling this")
            return

        self.recovery = gdb.FinishBreakpoint(one_before, internal=True)

    def __str__(self):
        return f"MANAGER:{self.name}"

    def frame_list(self):
        return '\n'.join(f"{i:>3}. {frame}" for i, frame in
                         enumerate(self.frames))

    def breakpoint_list(self):
        return '\n'.join(f" - {bp}" for bp in self.breakpoints)


class Frame:
    def __init__(self, manager, frame_type, start, breakpoint=None):

        self.manager = manager
        self.type = frame_type
        self.breakpoint = breakpoint

        self.frame = gdb.newest_frame()
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

        assert(self.start is None) # just being defensive
        if bp in self.args:
            self.do_arg(bp)
        elif bp in self.bodies:
            self.do_body(bp)
        elif bp == self.finish:
            self.do_finish(bp)

    def cares_about(self, bp):
        return bp in self.enabled or bp == self.finish or bp == self.start

    def up(self):
        '''
        ignore all inner breakpoints, go until finish breakpoint

        will still break on user defined breakpoints
        '''
        self.disable(*self.enabled)
        gdb.execute("continue")

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

    def do_start(self, bp):
        print("=== start ===")
        self.start = None
        self.finish = gdb.FinishBreakpoint(internal=True)

        self.enable()

    def do_arg(self, bp):
        raise NotImplementedError()

    def do_body(self, bp):
        raise NotImplementedError()

    def do_finish(self, bp):
        print("=== finish ===")
        ret = LispObject.create(bp.return_value)
        print(f"evaluation: {ret}")

        self.cleanup()

        #return
        if (self.type == FrameType.BREAKPOINT
            or self.type == FrameType.UNKNOWN):
            self.manager.rebuild()
        elif self.manager.empty():
            self.manager.rebuild()
        else:
            parent = self.manager.head().enable()

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

    def get_response(self):
        return input("step in? [yN] ") == "y"

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

        # print("IGNORE"*5)
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
        # print("\\" + "IGNORE"*5)


        if self.start:
            self.disable(*self.enabled)

            self.fun = None
        else:
            self.fun = LispFunction.create()
            print(f"FUNCTION: {self.fun}")

        self.expr_type = None

    def __str__(self):
        return f"[{self.fun.name() if self.fun else '-'}] : {super().__str__()}"

    def do_start(self, bp):
        self.fun = LispFunction.create()
        print(f"FUNCTION: {self.fun}")

        super().do_start(bp)

    def do_arg(self, bp):
        print("=== arg ===")

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

        #meat
        step_in = self.get_response()
        if not step_in:
            print("stepping over")
            return

        print("start point...")
        sub_start = gdb.Breakpoint("eval_sub", internal=True, temporary=True)

        #always an eval I think...
        subframe = EvalFrame(self.manager, FrameType.ARG, sub_start)
        self.step_in(subframe)

    def do_body(self, bp):
        print("=== body ===")

        self.set_expr_type(bp.location)

        #can't go back to arguments from a body
        for arg in self.args:
            arg.delete()
            self.args = set()

        #meat also
        step_in = self.get_response()
        if not step_in:
            print("stepping over")
            return

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

        self.line = None

    def do_start(self, bp):
        #TODO: maybe setup the manual C stuff here?

        super().do_start(bp)

    def do_body(self, bp):
        print("== body ==")

        step_in = self.get_response()
        if not step_in:
            print("stepping over")
            return

        #TODO: not really eval
        subframe_class = self.frame_wrapper(CFunctions(bp.location))
        subframe = subframe_class(self.manager, FrameType.BODY, None)

        self.step_in(subframe)

    def __str__(self):
        return f"[{self.subr}] : {super().__str__()}"



class LambdaFrame(Frame):
    def __init__(self, manager, frame_type, start, breakpoint=None):
        super().__init__(manager, frame_type, start, breakpoint=breakpoint)

        self.bodies = { gdb.Breakpont("eval_sub", internal=False) }

        if start:
            self.disable(*self.enabled)

    def do_body(self, bp):
        subframe = EvalFrame(self.manager, FrameType.BODY, None)

        self.step_in(subframe)


class SubrFrame(Frame):
    def __init__(self, manager, frame_type, start, breakpoint=None):
        super().__init__(manager, frame_type, start, breakpoint=breakpoint)

        func_addr = f"*{LispObject.raw_object(subr.function())}"
        self.bodies = { gdb.Breakpoint(func_addr, internal=False) }

        if start:
            self.disable(*self.enabled)
            self.subr = None
        else:
            subr = gdb.newest_frame().read_var("subr")
            self.subr = LispObject.create(subr)

    def do_start(self, bp):
        subr = gdb.newest_frame().read_var("subr")
        self.subr = LispObject.create(subr)

        super().do_start(bp)

    def do_body(self, bp):
        subframe = PrimitiveFrame(self.manager, self.subr, None)

        self.step_in(subframe)


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


class EventType(Enum):
    USER_BP = auto()
    INNER_BP = auto()
    RECOVERY_BP = auto()


try:
    for bp in man.breakpoints:
        if bp.is_valid():
            bp.delete()

    for frame in man.frames:
        frame.cleanup()

    gdb.events.stop.disconnect(man.hit)

    del(man)
    print("lemme clean that up for you :)")
except NameError:
    print("already clean :)")
finally:
    man=Manager()
