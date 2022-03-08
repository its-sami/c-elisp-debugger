import gdb

class LispBreakpoint(gdb.Breakpoint):
    def __init__(self, func_name: str, c_func: CFunctions):
        self.func_name = func_name
        self.c_func = c_func
        self.func_class = c_func.wrapper()

        print(f"set breakpoint: {self}")

        super().__init__(c_func.value)

    def stop(self):
        frame = gdb.newest_frame()

        return self.func_class.check_name(self.func_name)

    def __str__(self):
        return f"{self.func_name} [in {self.c_func.value}]"

    @staticmethod
    def create(func_name):
        return (LispBreakpoint(func_name, CFunctions.EVAL_SUB),
                LispBreakpoint(func_name, CFunctions.FUNCALL_SUBR))
