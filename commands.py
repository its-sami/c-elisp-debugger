import gdb

class PrintCommand(gdb.Command):
    def __init__(self):
        super().__init__("lisp-print", gdb.COMMAND_DATA, gdb.COMPLETE_COMMAND)

    def invoke(self, argument, from_tty):
        if argument == "":
            print("must pass in an argument")
            return

        try:
            val = gdb.selected_frame().read_var(argument)
            obj = LispObject.create(val)
            print(obj)
        except Exception as e:
            print(e)

class LookupCommand(gdb.Command):
    def __init__(self):
        super().__init__("lisp-lookup", gdb.COMMAND_DATA, gdb.COMPLETE_COMMAND)

    def invoke(self, argument, from_tty):
        pass

class BreakCommand(gdb.Command):
    def __init__(self, manager):
        super().__init__("lisp-break", gdb.COMMAND_BREAKPOINTS, gdb.COMPLETE_COMMAND)

        self.manager = manager

    def invoke(self, argument, from_tty):
        if argument:
            self.manager.breakpoint(argument)
        else:
            print("must give the name of a function!")

class BacktraceCommand(gdb.Command):
    def __init__(self, manager):
        super().__init__("lisp-backtrace", gdb.COMMAND_STACK, gdb.COMPLETE_COMMAND)

        self.manager = manager

    def invoke(self, argument, from_tty):
        if argument == "full":
            #TODO: this
            pass
        elif argument:
            print("invalid argument: [full]")
        else:
            print(self.manager.frame_list(backtrace=True))

class StepCommand(gdb.Command):
    def __init__(self, manager):
        super().__init__("lisp-step", gdb.COMMAND_RUNNING, gdb.COMPLETE_COMMAND)
        self.manager = manager

    def invoke(self, argument, from_tty):
        self.manager.step()

class NextCommand(gdb.Command):
    def __init__(self, manager):
        super().__init__("lisp-next", gdb.COMMAND_RUNNING, gdb.COMPLETE_COMMAND)
        self.manager = manager

    def invoke(self, argument, from_tty):
        self.manager.next()

class UpCommand(gdb.Command):
    def __init__(self, manager):
        super().__init__("lisp-up", gdb.COMMAND_RUNNING, gdb.COMPLETE_COMMAND)
        self.manager = manager

    def invoke(self, argument, from_tty):
        self.manager.up()

class ContinueCommand(gdb.Command):
    def __init__(self, manager):
        super().__init__("lisp-continue", gdb.COMMAND_RUNNING, gdb.COMPLETE_COMMAND)
        self.manager = manager

    def invoke(self, argument, from_tty):
        self.manager.cont()
