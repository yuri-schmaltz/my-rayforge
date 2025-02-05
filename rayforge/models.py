from render import Renderer


class WorkPiece:
    """
    A WorkPiece represents a real world work piece, It is usually
    loaded from an image file and serves as input for all other
    operations.
    """
    name: str
    data: bytes
    renderer: Renderer

    def __init__(self, name):
        self.name = name

    def get_aspect_ratio(self):
        return self.renderer.get_aspect_ratio(self.data)

    @staticmethod
    def from_file(filename, renderer):
        wp = WorkPiece(filename)
        with open(filename, 'rb') as fp:
            wp.data = renderer.prepare(fp.read())
        wp.renderer = renderer
        return wp


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
        self.paths.append(('move_to', x, y))

    def line_to(self, x, y):
        self.paths.append(('line_to', x, y))

    def close_path(self):
        self.paths.append(('close_path',))

    def dump(self):
        print(self.paths)


class WorkStep:
    """
    A WorkStep is a set of Processors that operate on a set of
    WorkPieces. It normally generates a Path in the end, but
    may also include processors that manipulate the input image.
    """
    name: str
    description: str = 'An operation on a group of workpieces'
    workpieces: list[WorkPiece]
    processors: list[str]
    path: Path

    def __init__(self, name):
        self.name = name
        self.workpieces = []
        self.processors = [
            'MakeTransparent',
            'ToGrayscale',
            'OutlineTracer',
        ]
        self.path = Path()

    def add_workpiece(self, workpiece: WorkPiece):
        self.workpieces.append(workpiece)


class Doc:
    """
    Represents a loaded Rayforge document.
    """
    workpieces: list[WorkPiece]
    worksteps: list[WorkStep]

    def __init__(self):
        self.workpieces = []
        self.worksteps = []

    def add_workstep(self, workstep):
        self.worksteps.append(workstep)

    def add_workpiece(self, workpiece):
        self.workpieces.append(workpiece)
