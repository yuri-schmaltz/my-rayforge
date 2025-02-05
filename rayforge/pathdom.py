import cairo


class PathDOM:
    def __init__(self):
        self.paths = []

    def clear(self):
        self.paths = []

    def move_to(self, x, y):
        self.paths.append(('move_to', x, y))

    def line_to(self, x, y):
        self.paths.append(('line_to', x, y))

    def close_path(self):
        self.paths.append(('close_path',))

    def dump(self):
        print(self.paths)

    def render(self, surface, scale_x, scale_y, ymax):
        # The path is in machine coordinates, i.e. zero point
        # at the bottom left, and units are mm.
        # Since Cairo coordinates put the zero point at the top left, we must
        # subtract Y from the machine's Y axis maximum.
        ctx = cairo.Context(surface)
        ctx.set_source_rgb(1, 0, 1)
        ctx.scale(scale_x, scale_y)

        ctx.set_line_width(1/scale_x)
        for opname, *args in self.paths:
            op = getattr(ctx, opname)
            if opname in ('move_to', 'line_to'):
                args[1] = ymax-args[1]  # zero point correction
            op(*args)
            if opname == 'close_path':
                ctx.stroke()
