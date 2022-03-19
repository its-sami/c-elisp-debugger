import gdb
from enum import Enum, auto

class Manager:
    def __init__(self, name):
        self.name = name

        self.breakpoints = []
        self.recovery = None
        self.disabled = set()

        self.frames = []

        gdb.events.stop.connect(self.hit)

    #MARK: breakpoint stuff

    #TODO: maybe need to make this the only listener?
    # could subclass internal breakpoints, and pass around frames
    # ALL THIS TO AVOID doubling up on breakpoints
    # i.e. user wants to debug an argument
    # but that's a function they've breakpointed
    def hit(self, event):
        if not isinstance(event, gdb.BreakpointEvent):
            return

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

        # need to figure out priorities of breakpoints
        if bps := events[EventType.RECOVERY_BP]:
            print("wow we made it :)")
            self.recovery = None
            frame = EvalFrame(self, FrameType.UNKNOWN, None)
            self.push(frame)
        elif bps := events[EventType.USER_BP]:
            bp = bps[0] #TODO: can i just use the first one?
            print("ding ding ding")
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
        else:
            raise Exception("invalid event hit")

    def breakpoint(self, func_name):
        existing = [ bp for bp in self.breakpoints if bp.func_name == func_name ]

        if existing:
            assert len(existing) == 2
            eval, subr = existing

            #should always be in this order
            assert eval.c_func == CFunctions.EVAL_SUB
            assert subr.c_func == CFunctions.FUNCALL_SUBR
        else:
            eval, subr = LispBreakpoint.create(func_name)

            self.breakpoints.append(eval)
            self.breakpoints.append(subr)

        return (eval, subr)

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

    def enabled(self):
        return [bp for bp in self.breakpoints if bp.enabled]

    # /breakpoint stuff

    #MARK: stack stuff

    def push(self, frame):
        if self.full():
            self.head().disable()

        self.frames.append(frame)

    def pop(self):
        frame =  self.frames.pop()

        #return
        if (frame.type == FrameType.BREAKPOINT
            or frame.type == FrameType.UNKNOWN):
            self.rebuild()
        elif self.empty():
            self.rebuild()
        else:
            self.head().enable()

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
                    return (frame, CFunctions(frame.name()))

        prev = find_prev_frame(gdb.newest_frame())
        if prev is None:
            print("no more frames to use")
            return

        frame, func = prev

        if self.full() and self.head().frame == frame:
            print("everything already cool")
            return

        if (one_before := frame.newer()) is None:
            print("weird case (already at the top of the stack)... make sure you've popped before calling this")
            return

        #self.recovery = gdb.FinishBreakpoint(one_before, internal=True)

        # to recover just create a new frame
        # just set that frame to start when program execution
        # returns to the underlying frame
        func_frame = Frame.frame_wrapper(func)
        recovery = gdb.FinishBreakpoint(one_before, internal=True)
        recovery_frame = func_frame(self, FrameType.UNKNOWN, recovery)

        self.push(recovery_frame)
        gdb.execute("continue")

    # /stack stuff

    #MARK: navigation

    def in_guts(self):
        return (self.full()
                and isinstance(self.head(), PrimitiveFrame)
                and self.head().guts)

    def step(self):
        if self.empty():
            print("get into lisp first!")
        elif self.in_guts():
            print("in C mode; use regular navigation commands (or lisp-continue)")
        else:
            self.head().step()

    def next(self):
        if self.empty():
            print("get into lisp first!")
        elif self.in_guts():
            print("in C mode; use regular navigation commands")
            print("(lisp-up or lisp-continue also work)")
        else:
            self.head().next()

    def up(self):
        if self.empty():
            print("get into lisp first!")
        else:
            self.head().up()

    def cont(self):
        if not (self.enabled()
                or self.recovery):
            print("get into lisp first!")
        elif self.full():
            self.head().cont()
        else:
            gdb.execute("continue")

    # /navigation

    #MARK: printing stuff

    def __str__(self):
        return f"MANAGER:{self.name}"

    def frame_list(self, backtrace=False):
        if backtrace:
            frames = reversed(self.frames)
        else:
            frames = self.frames

        return '\n'.join(f"{i:>3}. {frame}" for i, frame in enumerate(frames))

    def breakpoint_list(self):
        return '\n'.join(f" - {bp}" for bp in self.breakpoints)


class EventType(Enum):
    USER_BP = auto()
    INNER_BP = auto()
    RECOVERY_BP = auto()
