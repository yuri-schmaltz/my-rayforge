from typing import List
from ..config import config
from ..modifier import Modifier, \
                       MakeTransparent, \
                       ToGrayscale, \
                       OutlineTracer, \
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

    def __init__(self, name):
        self.name: str = name
        self.visible: bool = True
        self.modifiers: List[Modifier] = []
        self.path: Path = Path()
        self.laser: Laser = None

        self.changed = Signal()
        self.set_laser(config.machine.heads[0])

        self.power: int = self.laser.max_power
        self.cut_speed: int = config.machine.max_cut_speed
        self.travel_speed: int = config.machine.max_travel_speed
        self.air_assist: bool = False

    @staticmethod
    def for_outline():
        workstep = WorkStep('Outline')
        workstep.modifiers = [
            MakeTransparent(),
            ToGrayscale(),
            OutlineTracer(),
        ]
        return workstep

    @staticmethod
    def for_rasterizing():
        workstep = WorkStep('Raster Engrave')
        workstep.modifiers = [
            MakeTransparent(),
            ToGrayscale(),
            Rasterizer(),
        ]
        return workstep

    def set_visible(self, visible=True):
        self.visible = visible
        self.changed.send(self, workstep=self)

    def set_laser(self, laser):
        self.laser = laser
        laser.changed.connect(self._on_laser_changed)
        self.changed.send(self)

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


class WorkPlan:
    """
    Represents a sequence of worksteps.
    """
    def __init__(self, name):
        self.name: str = name
        self.worksteps: List[WorkStep] = [
            WorkStep.for_outline(),
            WorkStep.for_rasterizing(),
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
