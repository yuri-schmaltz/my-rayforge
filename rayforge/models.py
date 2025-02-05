import cairo
from dataclasses import field
from render import Renderer
from processor import processor_by_name


class WorkPiece:
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
    workpieces: list[WorkPiece]
    worksteps: list[WorkStep]

    def __init__(self):
        self.workpieces = []
        self.worksteps = []

    def add_workstep(self, workstep):
        self.worksteps.append(workstep)

    def add_workpiece(self, workpiece):
        self.workpieces.append(workpiece)
