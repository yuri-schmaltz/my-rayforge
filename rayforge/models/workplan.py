from __future__ import annotations
from typing import List
from ..config import config, getflag
from ..modifier import Modifier, MakeTransparent, ToGrayscale
from ..opsproducer import OpsProducer, OutlineTracer, EdgeTracer, Rasterizer
from ..opstransformer import OpsTransformer, Optimize, Smooth, ArcWeld
from .renderable import Renderable
from .machine import Laser
from .ops import Ops
from blinker import Signal


DEBUG_OPTIMIZE = getflag('DEBUG_OPTIMIZE')
DEBUG_SMOOTH = getflag('DEBUG_SMOOTH')
DEBUG_ARCWELD = getflag('DEBUG_ARCWELD')


class WorkStep:
    """
    A WorkStep is a set of Modifiers that operate on a set of
    WorkPieces. It normally generates a Ops in the end, but
    may also include modifiers that manipulate the input image.
    """
    typelabel = None

    def __init__(self, opsproducer: OpsProducer, name=None):
        self.workplan: WorkPlan = None
        self.name: str = name or self.typelabel
        self.visible: bool = True
        self.modifiers: List[Modifier] = [
            MakeTransparent(),
            ToGrayscale(),
        ]
        self._modifier_ref_for_pyreverse: Modifier
        self.opsproducer: OpsProducer = opsproducer
        self.opstransformers: List[OpsTransformer] = []
        self._opstransformer_ref_for_pyreverse: OpsTransformer
        self.passes: int = 1
        self.laser: Laser = None

        self.changed = Signal()
        self.set_laser(config.machine.heads[0])

        self.power: int = self.laser.max_power
        self.cut_speed: int = config.machine.max_cut_speed
        self.travel_speed: int = config.machine.max_travel_speed
        self.air_assist: bool = False

        if DEBUG_OPTIMIZE:
            self.opstransformers.append(Optimize())
        if DEBUG_SMOOTH:
            self.opstransformers.append(Smooth())
        if DEBUG_ARCWELD:
            self.opstransformers.append(ArcWeld())

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

    def run(self, surface, pixels_per_mm):
        """
        surface: the input surface to operate on.
        pixels_per_mm: tuple containing pixels_per_mm_x and pixels_per_mm_y
        """
        ops = Ops()
        ops.set_power(self.power)
        ops.set_cut_speed(self.cut_speed)
        ops.set_travel_speed(self.travel_speed)
        ops.enable_air_assist(self.air_assist)

        # Apply bitmap modifiers.
        for modifier in self.modifiers:
            modifier.run(surface)

        # Produce an Ops object from the resulting surface.
        ops += self.opsproducer.run(
            config.machine,
            self.laser,
            surface,
            pixels_per_mm
        )

        # Apply Ops object transformations.
        for transformer in self.opstransformers:
            transformer.run(ops)

        ops.disable_air_assist()
        return ops

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
        super().__init__(OutlineTracer(), name, **kwargs)


class Contour(WorkStep):
    typelabel = "Contour"

    def __init__(self, name=None, **kwargs):
        super().__init__(EdgeTracer(), name, **kwargs)


class Rasterize(WorkStep):
    typelabel = "Raster Engrave"

    def __init__(self, name=None, **kwargs):
        super().__init__(Rasterizer(), name, **kwargs)


class WorkPlan:
    """
    Represents a sequence of worksteps.
    """
    def __init__(self, name):
        self.name: str = name
        self.renderables: List[Renderable] = []
        self._renderable_ref_for_pyreverse: Renderable
        self.worksteps: List[WorkStep] = []
        self._workstep_ref_for_pyreverse: WorkStep
        self.changed = Signal()
        self.add_workstep(Contour())

    def __iter__(self):
        return iter(self.worksteps)

    def add_renderable(self, renderable: Renderable):
        self.renderables.append(renderable)
        self.changed.send(self)

    def remove_renderable(self, renderable: Renderable):
        self.renderables.remove(renderable)
        self.changed.send(self)

    def add_workstep(self, workstep):
        self.worksteps.append(workstep)
        workstep.workplan = self
        self.changed.send(self)

    def remove_workstep(self, workstep):
        self.worksteps.remove(workstep)
        workstep.workplan = None
        self.changed.send(self)

    def set_worksteps(self, worksteps):
        """
        Replace all worksteps.
        """
        self.worksteps = worksteps
        self.changed.send(self)

    def execute(self, optimize=True):
        pixels_per_mm = 50
        for renderable in self.renderables:
            surface, _ = renderable.render(pixels_per_mm, pixels_per_mm)
            ops = Ops()
            for step in self.worksteps:
                step_ops = step.run(surface, (pixels_per_mm, pixels_per_mm))
                if optimize:
                    Optimize().run(step_ops)
                ops += step_ops*step.passes
        return ops

    def has_steps(self):
        return len(self.worksteps) > 0
