from typing import List
from ..config import config
from ..modifier import Modifier, \
                       MakeTransparent, \
                       ToGrayscale, \
                       OutlineTracer, \
                       EdgeTracer, \
                       Rasterizer
from .machine import Laser
from .workpiece import WorkPiece
from .path import Path
from blinker import Signal


class WorkStep:
    """
    A WorkStep is a set of Modifiers that operate on a set of
    WorkPieces. It normally generates a Path in the end, but
    may also include modifiers that manipulate the input image.
    """
    typelabel = None

    def __init__(self, name=None):
        self.name: str = name or self.typelabel
        self.visible: bool = True
        self.modifiers: List[Modifier] = []
        self.passes: int = 1
        self.path: Path = Path()
        self.laser: Laser = None

        self.changed = Signal()
        self.set_laser(config.machine.heads[0])

        self.power: int = self.laser.max_power
        self.cut_speed: int = config.machine.max_cut_speed
        self.travel_speed: int = config.machine.max_travel_speed
        self.air_assist: bool = False

    def set_passes(self, passes=True):
        self.passes = int(passes)
        self.changed.send(self)

    def set_visible(self, visible=True):
        self.visible = visible
        self.changed.send(self)

    def set_laser(self, laser):
        self.laser = laser
        laser.changed.connect(self._on_laser_changed)
        self.changed.send(self)

    def set_power(self, power):
        self.power = power
        self.changed.send(self)

    def run(self, surface, pixels_per_mm, ymax):
        """
        surface: the input surface containing an image that the
        modifiers should modify (or convert to a path).
        pixels_per_mm: tuple containing pixels_per_mm_x and pixels_per_mm_y
        ymax: machine max y size (for Z axis inversion)
        """
        self.path.clear()
        self.path.set_power(self.power)
        self.path.set_cut_speed(self.cut_speed)
        self.path.set_travel_speed(self.travel_speed)
        self.path.enable_air_assist(self.air_assist)
        for modifier in self.modifiers:
            modifier.run(self, surface, pixels_per_mm, ymax)
        self.path.disable_air_assist()

    def _on_laser_changed(self, sender, **kwargs):
        self.changed.send(self)

    def get_summary(self):
        power = int(self.power/self.laser.max_power*100)
        speed = int(self.cut_speed)
        return f"{power}% power, {speed} mm/min"

    def dump(self, indent=0):
        print("  "*indent, self.name)
        for workpiece in self.workpieces:
            workpiece.dump(1)


class Outline(WorkStep):
    typelabel = "External Outline"

    def __init__(self, name=None, **kwargs):
        super().__init__(name, **kwargs)
        self.modifiers = [
            MakeTransparent(),
            ToGrayscale(),
            OutlineTracer(),
        ]


class Contour(WorkStep):
    typelabel = "Contour"

    def __init__(self, name=None, **kwargs):
        super().__init__(name, **kwargs)
        self.modifiers = [
            MakeTransparent(),
            ToGrayscale(),
            EdgeTracer(),
        ]


class Rasterize(WorkStep):
    typelabel = "Raster Engrave"

    def __init__(self, name=None, **kwargs):
        super().__init__(name, **kwargs)
        self.modifiers = [
            MakeTransparent(),
            ToGrayscale(),
            Rasterizer(),
        ]


class WorkPlan:
    """
    Represents a sequence of worksteps.
    """
    def __init__(self, name):
        self.name: str = name
        self.worksteps: List[WorkStep] = [
            Outline(),
            Rasterize(),
        ]
        self.changed = Signal()

    def __iter__(self):
        return iter(self.worksteps)

    def add_workstep(self, workstep):
        self.worksteps.append(workstep)
        self.changed.send(self)

    def remove_workstep(self, workstep):
        self.worksteps.remove(workstep)
        self.changed.send(self)

    def set_worksteps(self, worksteps):
        """
        Replace all worksteps.
        """
        self.worksteps = worksteps
        self.changed.send(self)

    def get_result(self, optimize=True):
        path = Path()
        for step in self.worksteps:
            if optimize:
                step.path.optimize()
            path += step.path*step.passes
        return path
