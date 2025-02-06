from render import Renderer
from modifier import Modifier, MakeTransparent, ToGrayscale, OutlineTracer


class LaserHead:
    min_power: int = 0
    max_power: int = 1000  # Max power (0-1000 for GRBL)


class Machine:
    name: str
    preamble: list[str] = ["G21 ; Set units to mm", "G90 ; Absolute positioning"]
    postscript: list[str] = ["G0 X0 Y0 ; Return to origin"]
    heads: list[LaserHead]
    max_travel_speed: int = 3000   # in mm/min
    max_cut_speed: int = 1000   # in mm/min
    dimensions: tuple[int, int] = 200, 200

    def __init__(self):
        self.heads = [LaserHead()]


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

    def dump(self, indent=0):
        print("  "*indent, self.name, self.renderer.label)


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
    A WorkStep is a set of Modifiers that operate on a set of
    WorkPieces. It normally generates a Path in the end, but
    may also include modifiers that manipulate the input image.
    """
    name: str
    description: str = 'An operation on a group of workpieces'
    workpieces: list[WorkPiece]
    modifiers: list[Modifier]
    path: Path

    def __init__(self, name):
        self.name = name
        self.workpieces = []
        self.modifiers = [
            MakeTransparent(),
            ToGrayscale(),
            OutlineTracer(),
        ]
        self.path = Path()

    def add_workpiece(self, workpiece: WorkPiece):
        self.workpieces.append(workpiece)

    def remove_workpiece(self, workpiece):
        self.workpieces.remove(workpiece)

    def dump(self, indent=0):
        print("  "*indent, self.name)
        for workpiece in self.workpieces:
            workpiece.dump(1)


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

    def add_workpiece(self, workpiece, workstep=None):
        self.workpieces.append(workpiece)
        if workstep:
            workstep.add_workpiece(workpiece)

    def has_workpiece(self):
        return bool(self.workpieces)
