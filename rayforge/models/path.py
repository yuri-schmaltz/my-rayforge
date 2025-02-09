class Path:
    """
    Represents a set of generated paths that are used for
    making gcode, but also to generate vactor graphics for display.
    """
    def __init__(self):
        self.paths = []

    def clear(self):
        self.paths = []

    def move_to(self, x, y):
        self.paths.append(('move_to', float(x), float(y)))

    def line_to(self, x, y):
        self.paths.append(('line_to', float(x), float(y)))

    def close_path(self):
        self.paths.append(('close_path',))

    def dump(self):
        print(self.paths)
