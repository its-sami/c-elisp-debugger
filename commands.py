import gdb

class PrintCommand(gdb.Command):
    def __init__(self):
        super().__init__("lisp-print", gdb.COMMAND_DATA)

    def invoke(self, argument, from_tty):
        args = argument.split(" ")

        if len(args) == 1:
            self.print_lisp(args[0])
        elif len(args) == 2 and args[0] == "internal":
            self.print_c(args[1])
        else:
            print("invalid usage: lisp-print (<var-name> | internal <var-name>)")

    def print_lisp(self, name):
        val = VariableLookup.get_val(name)

        if val is None:
            print(f"object {name} does not exist")
        else:
            print(val)

    def print_c(self, name):
        try:
            obj = LispObject.from_var(name)
            print(obj)
        except ValueError:
            print(f"variable {name} does not exist")

class BreakCommand(gdb.Command):
    def __init__(self, manager):
        super().__init__("lisp-break", gdb.COMMAND_BREAKPOINTS)

        self.manager = manager

    def invoke(self, argument, from_tty):
        if argument:
            self.manager.breakpoint(argument)
        else:
            print("must give the name of a function!")

class BacktraceCommand(gdb.Command):
    def __init__(self, manager):
        super().__init__("lisp-backtrace", gdb.COMMAND_STACK)

        self.manager = manager
        self.filter = LispFrameFilter(enabled=False)

    def invoke(self, argument, from_tty):
        if argument == "current":
            print(self.manager.frame_list(backtrace=True))
        elif argument:
            print("invalid argument: [current]")
        else:
            self.filter.enabled = True
            gdb.execute("backtrace")
            self.filter.enabled = False

class StepCommand(gdb.Command):
    def __init__(self, manager):
        super().__init__("lisp-step", gdb.COMMAND_RUNNING)
        self.manager = manager

    def invoke(self, argument, from_tty):
        self.manager.step()

class NextCommand(gdb.Command):
    def __init__(self, manager):
        super().__init__("lisp-next", gdb.COMMAND_RUNNING)
        self.manager = manager

    def invoke(self, argument, from_tty):
        self.manager.next()

class UpCommand(gdb.Command):
    def __init__(self, manager):
        super().__init__("lisp-up", gdb.COMMAND_RUNNING)
        self.manager = manager

    def invoke(self, argument, from_tty):
        self.manager.up()

class ContinueCommand(gdb.Command):
    def __init__(self, manager):
        super().__init__("lisp-continue", gdb.COMMAND_RUNNING)
        self.manager = manager

    def invoke(self, argument, from_tty):
        self.manager.cont()
