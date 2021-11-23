import gdb
from gdb.FrameDecorator import FrameDecorator

class LispFrameFilter:
    def __init__(self):
        self.name = "lisp-objects"
        self.enabled = True
        self.priority = 100

        gdb.frame_filters[self.name] = self

    def filter(self, frames):
        for frame in frames:
            if CFunctions.cool_func(frame.function()):
                yield LispFrameDecorator(frame.inferior_frame())

class LispFrameDecorator(FrameDecorator):
    def __init__(self, frame: gdb.Frame):
        super().__init__(frame)

        self.lisp_function = LispFunction.create(frame)

        print(f"building decorator: {self.lisp_function}")

    def address(self):
        return None

    def filename(self):
        return None

    def line(self):
        return None

    def function(self):
        #print(self.lisp_function.name(), type(self.lisp_function))
        return self.lisp_function.name()

    def frame_args(self):
        #print(self.lisp_function.args_list(), type(self.lisp_function))
        return self.lisp_function.args_list()
