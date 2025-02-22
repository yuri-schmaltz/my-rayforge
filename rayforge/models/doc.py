import cairo
from typing import List
from blinker import Signal
from ..config import config
from .workpiece import WorkPiece
from .workplan import WorkPlan


class Doc:
    """
    Represents a loaded Rayforge document.
    """
    workpieces: List[WorkPiece]
    workplan: WorkPlan

    def __init__(self):
        self.workpieces: List[WorkPiece] = []
        self._workpiece_ref_for_pyreverse: WorkPiece
        self.workplan: WorkPlan = WorkPlan("Default plan")
        self.surface: cairo.Surface = None
        self.changed = Signal()
        self.workplan.changed.connect(self.changed.send)

    def __iter__(self):
        return iter(self.workpieces)

    def add_workpiece(self, workpiece):
        self.workpieces.append(workpiece)

    def remove_workpiece(self, workpiece):
        if workpiece in self.workpieces:
            self.workpieces.remove(workpiece)

    def has_workpiece(self):
        return bool(self.workpieces)

    def has_result(self):
        return self.workplan.has_result()

    def render(self,
               pixels_per_mm_x: int,
               pixels_per_mm_y: int,
               force: bool = False):
        surface_width_mm, surface_height_mm = config.machine.dimensions
        width = surface_width_mm * pixels_per_mm_x
        height = surface_height_mm * pixels_per_mm_y

        if self.surface \
                and self.surface.get_width() == width \
                and self.surface.get_height() == height \
                and not force:
            return self.surface, False

        self.surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, width, height)
        for workpiece in self.workpieces:
            surface, changed = workpiece.render(pixels_per_mm_x,
                                                pixels_per_mm_y,
                                                force)
            if changed:
                pos_x_mm, pos_y_mm = workpiece.pos
                pos_x = pos_x_mm * pixels_per_mm_x
                pos_y = pos_y_mm * pixels_per_mm_y
                ctx = cairo.Context(self.surface)
                ctx.set_source_surface(surface, pos_x, pos_y)
                ctx.paint()

        return self.surface, True

    def save_bitmap(self, filename, pixels_per_mm_x, pixels_per_mm_y):
        surface, changed = self.render(pixels_per_mm_x, pixels_per_mm_y)
        surface.write_to_png(filename)
