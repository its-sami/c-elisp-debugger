import gdb

try:
    resp = input("removing all breakpoints, do you want to proceed? [y/N] > ").strip().lower()

    if resp != "y":
        raise Exception("user skipped cleanup")

    for bp in gdb.breakpoints():
        bp.delete()

    gdb.events.stop.disconnect(man.hit)

    print("cleaned up the last stuff")
except Exception:
    pass
