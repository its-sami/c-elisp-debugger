class LispBreakpoint(gdb.Breakpoint):
    def __init__(self, func_name: str, c_func: str):
        super().__init__(c_func)

        self.func_name = func_name
        self.c_func = c_func

    def stop(self):
        frame = gdb.newest_frame()
        assert frame.name() == self.c_func
        assert CFunctions.cool_func(self.c_func)

        func_class = CFunctions(self.c_func).wrapper()
        self.func = func_class(frame)

        return self.func.name() == self.func_name
