import gdb

class LispBreakpoint(gdb.Breakpoint):
    def __init__(self, func_name: str, c_func_name: str):
        assert CFunctions.cool_func(c_func_name)

        self.func_name = func_name
        self.c_func_name = c_func_name
        self.c_func = CFunctions(c_func_name).wrapper()

        print(f"set breakpoint: {self.func_name}[@{self.c_func_name}:{self.c_func}]")

        super().__init__(c_func_name)

    def stop(self):
        frame = gdb.newest_frame()

        return self.c_func.check_name(self.func_name)
