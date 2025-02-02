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

    def render(self, surface, scale, ymax):
        ctx = cairo.Context(surface)
        ctx.set_source_rgb(1, 0, 1)
        ctx.scale(scale, scale)

        ctx.set_line_width(2/scale)
        for opname, *args in self.paths:
            op = getattr(ctx, opname)
            if opname in ('move_to', 'line_to'):
                args[1] = ymax-args[1]
            op(*args)
            if opname == 'close_path':
                ctx.stroke()
