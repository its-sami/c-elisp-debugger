import gdb

if __name__ == "__main__":
    # SETTING UP VARIABLES
    man = Manager("MAIN")

    # REGISTERING COMMANDS
    PrintCommand()
    BacktraceCommand(man)

    BreakCommand(man)
    StepCommand(man)
    NextCommand(man)
    UpCommand(man)
    ContinueCommand(man)
