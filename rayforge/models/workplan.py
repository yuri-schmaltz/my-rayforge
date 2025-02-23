from __future__ import annotations
from typing import List, Dict
from copy import deepcopy
from ..asyncloop import run_async
from ..config import config, getflag
from ..modifier import Modifier, MakeTransparent, ToGrayscale
from ..opsproducer import OpsProducer, OutlineTracer, EdgeTracer, Rasterizer
from ..opstransformer import OpsTransformer, Optimize, Smooth, ArcWeld
from .workpiece import WorkPiece
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
        # Map WorkPieces to Ops and size
        self.ops: Dict[WorkPiece, [Ops, [float, float]]] = {}
        self._workpiece_ref_for_pyreverse: WorkPiece
        self.passes: int = 1
        self.pixels_per_mm = 25, 25
        self.laser: Laser = None

        self.changed = Signal()
        self.ops_changed: Signal = Signal()
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
        self._on_changed()

    def set_visible(self, visible=True):
        self.visible = visible
        self._on_changed()

    def set_laser(self, laser):
        self.laser = laser
        laser.changed.connect(self._on_laser_changed)
        self._on_changed()

    def set_power(self, power):
        self.power = power
        self._on_changed()

    def workpieces(self):
        return self.ops.keys()

    def execute(self, workpiece) -> [Ops, [float, float]]:
        """
        workpiece: the input workpiece to generate Ops for.
        """
        if self.can_scale():
            # Size does not matter unless it is so small that rounding
            # errors become relevant. So to be able to handle very small
            # images gracefull, we just assume a fixed size for the off
            # screen rendering. Later it is scaled for display anyway.
            size = 50, 50  # in mm
        else:  # Render at current size in canvas
            size = workpiece.size
        surface, _ = workpiece.render(*self.pixels_per_mm,
                                       size=size,
                                       force=True)

        # There is no guarantee that the renderer was able to delivered
        # the size we asked for. Check the actual size.
        width, height = surface.get_width(), surface.get_height()
        width_mm = width / self.pixels_per_mm[0]
        height_mm = height / self.pixels_per_mm[1]
        size = width_mm, height_mm

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
            self.pixels_per_mm
        )

        # Apply Ops object transformations.
        for transformer in self.opstransformers:
            transformer.run(ops)

        ops.disable_air_assist()
        self.ops[workpiece] = ops, size
        return ops, size

    async def execute_async(self, workpiece: WorkPiece) -> [
            WorkPiece, Ops, [float, float]]:
        ops, size = self.execute(workpiece)
        return workpiece, ops, size

    def _on_changed(self):
        if not self.workplan:
            return
        for workpiece in self.workplan.workpieces:
            run_async(self.execute_async(workpiece), self._on_ops_created)
        self.changed.send(self)

    def _on_ops_created(self, result):
        workpiece, ops, size = result
        self.ops_changed.send(self, workpiece=workpiece)
        return False

    def trigger_changed(self):
        self.changed.send(self)

    def get_ops(self, workpiece):
        """
        Returns Ops for the given workpiece, scaled to the size of
        the workpiece.
        Returns None if no Ops were made yet.
        """
        ops, size = self.ops.get(workpiece, (None, None))
        if ops is None:
            return None
        orig_width_mm, orig_height_mm = size
        width_mm, height_mm = workpiece.size
        ops = deepcopy(ops)
        ops.scale(width_mm/orig_width_mm, height_mm/orig_height_mm)
        return ops

    def _on_laser_changed(self, sender, **kwargs):
        self._on_changed()

    def get_summary(self):
        power = int(self.power/self.laser.max_power*100)
        speed = int(self.cut_speed)
        return f"{power}% power, {speed} mm/min"

    def can_scale(self):
        return self.opsproducer.can_scale()

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
        self.workpieces: List[WorkPiece] = []
        self._workpiece_ref_for_pyreverse: WorkPiece
        self.worksteps: List[WorkStep] = []
        self._workstep_ref_for_pyreverse: WorkStep
        self.changed = Signal()
        self.add_workstep(Contour())

    def __iter__(self):
        return iter(self.worksteps)

    def add_workpiece(self, workpiece: WorkPiece):
        self.workpieces.append(workpiece)
        workpiece.size_changed.connect(self._on_workpiece_size_changed)
        self.changed.send(self)

    def remove_workpiece(self, workpiece: WorkPiece):
        workpiece.size_changed.disconnect(self._on_workpiece_size_changed)
        self.workpieces.remove(workpiece)
        self.changed.send(self)

    def _on_workpiece_size_changed(self, workpiece):
        for step in self.worksteps:
            if not step.can_scale():
                step._on_changed()

    def add_workstep(self, workstep):
        workstep.workplan = self
        self.worksteps.append(workstep)
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
        for step in worksteps:
            step.workplan = self
        self.changed.send(self)

    def has_steps(self):
        return len(self.worksteps) > 0

    def execute(self, optimize=True):
        ops = Ops()
        for workpiece in self.workpieces:
            for step in self.worksteps:
                step.execute(workpiece)
                step_ops = step.get_ops(workpiece)
                x, y = workpiece.pos
                ymax = config.machine.dimensions[1]
                translate_y = ymax - y - workpiece.size[1]
                step_ops.translate(x, translate_y)
                if optimize:
                    Optimize().run(step_ops)
                ops += step_ops*step.passes
        return ops
