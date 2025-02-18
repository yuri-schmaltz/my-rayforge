from gi.repository import Graphene
import cairo
from dataclasses import dataclass
from ..opsencoder.cairoencoder import CairoEncoder
from ..config import config
from .canvas import Canvas, CanvasElement


def _copy_surface(source, target, width, height, clip, crop_region):
    in_width, in_height = source.get_width(), source.get_height()
    scale_x = width/in_width
    scale_y = height/in_height
    ctx = cairo.Context(target)
    clip_x, clip_y, clip_w, clip_h = clip
    ctx.rectangle(0, 0, clip_x+clip_w, clip_y+clip_h)
    ctx.clip()
    crop_x, crop_y, crop_w, crop_h = crop_region
    ctx.rectangle(0, 0, crop_x+crop_w, crop_y+crop_h)
    ctx.clip()
    ctx.scale(scale_x, scale_y)
    ctx.set_source_surface(source, crop_x, crop_y)
    ctx.paint()
    return target


@dataclass
class WorkPieceElement(CanvasElement):
    """
    WorkPieceElements display WorkPiece objects on the WorkSurface.
    This is the "standard" element used to display workpieces on the
    WorkSurface.
    """

    def render(self, clip):
        assert self.surface is not None
        width, height = self.size_px()
        workpiece = self.data
        renderer = workpiece.renderer
        surface = renderer.render_workpiece(workpiece, width, height)
        if not surface:
            return self.surface  # we assume surface was changed in-place
        self.surface = _copy_surface(surface,
                                     self.surface,
                                     width,
                                     height,
                                     clip,
                                     self.crop_region_px())
        return self.surface


@dataclass
class WorkStepElement(CanvasElement):
    """
    WorkStepElements display the result of a WorkStep on the
    WorkSurface. WorkSteps produce output such as the laser path,
    but can also include bitmap modifiers such as converting from color
    to grayscale.
    """

    def render(self, clip):
        # Make a copy of the Cairo surface that contains all workpieces.
        super().render(clip)
        width, height = self.size_px()
        workpiece_surface = self.canvas.workpiece_elements.surface
        assert width == workpiece_surface.get_width()
        assert height == workpiece_surface.get_height()
        self.surface = _copy_surface(workpiece_surface,
                                     self.surface,
                                     width,
                                     height,
                                     clip,
                                     self.crop_region_px())

        # Let the workstep process our surface in-place.
        width, height = self.size_px()
        pixels_per_mm = self.get_pixels_per_mm()
        workstep = self.data
        workstep.run(config.machine, self.surface, pixels_per_mm)

        # If Ops were generated, render only it. i.e. clear the current
        # bitmap.
        if workstep.ops:
            self.allocate(True)
            encoder = CairoEncoder()
            encoder.encode(workstep.ops,
                           config.machine,
                           self.surface,
                           self.get_pixels_per_mm())

        return self.surface


class WorkSurface(Canvas):
    """
    The WorkSurface displays a grid area with
    WorkPieces and WorkStep results according to real world
    dimensions.
    """
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.workpiece_elements = CanvasElement(
            *self.root.rect(),
            selectable=False
        )
        self.root.add(self.workpiece_elements)
        self.grid_size = 10  # in mm
        self.update()

    def set_size(self, width_mm, height_mm):
        self.root.set_size(width_mm, height_mm)
        for elem in self.root.children:
            if isinstance(elem, WorkStepElement):
                elem.set_size(width_mm, height_mm)
        self.update()

    def update(self):
        self.aspect_ratio = self.root.width_mm/self.root.height_mm
        self.workpiece_elements.width_mm = self.root.width_mm
        self.workpiece_elements.height_mm = self.root.height_mm
        self.root.allocate()
        self.queue_draw()

    def add_workstep(self, workstep):
        """
        Adds the workstep, but only if it does not yet exist.
        Also adds each of the WorkPieces, but only if they
        do not exist.
        """
        # Add or find the WorkStep.
        if not self.find_by_data(workstep):
            elem = WorkStepElement(*self.root.rect(),
                                   data=workstep,
                                   selectable=False)
            self.add(elem)
            workstep.changed.connect(self.on_workstep_changed)
        self.queue_draw()

    def on_workstep_changed(self, workstep, **kwargs):
        elem = self.find_by_data(workstep)
        if not elem:
            return
        elem.visible = workstep.visible
        self.queue_draw()

    def add_workpiece(self, workpiece):
        """
        Adds a workpiece.
        """
        if self.workpiece_elements.find_by_data(workpiece):
            self.queue_draw()
            return
        width_mm, height_mm = workpiece.get_natural_size()
        if width_mm is None or height_mm is None:
            aspect_ratio = workpiece.get_aspect_ratio()
            width_mm, height_mm = self.root.get_max_child_size(aspect_ratio)
        elem = WorkPieceElement(self.root.width_mm/2-width_mm/2,
                                self.root.height_mm/2-height_mm/2,
                                width_mm,
                                height_mm,
                                data=workpiece)
        self.workpiece_elements.add(elem)
        self.queue_draw()

    def clear_workpieces(self):
        self.workpiece_elements.clear()
        self.queue_draw()

    def clear(self):
        self.root.clear()
        self.queue_draw()

    def find_by_type(self, thetype):
        return [c for c in self.root.children if isinstance(c, thetype)]

    def set_workpieces_visible(self, visible=True):
        self.workpiece_elements.visible = visible
        self.queue_draw()

    def do_snapshot(self, snapshot):
        # Create a Cairo context for the snapshot
        width, height = self.get_width(), self.get_height()
        bounds = Graphene.Rect().init(0, 0, width, height)
        ctx = snapshot.append_cairo(bounds)

        self.pixels_per_mm_x = width/self.root.width_mm
        self.pixels_per_mm_y = height/self.root.height_mm
        self._draw_grid(ctx, width, height)

        super().do_snapshot(snapshot)

    def _draw_grid(self, ctx, width, height):
        """
        Draw scales on the X and Y axes.
        """
        # Draw vertical lines
        for x in range(0, int(self.root.width_mm)+1, self.grid_size):
            x_px = x*self.pixels_per_mm_x
            ctx.move_to(x_px, 0)
            ctx.line_to(x_px, height)
            ctx.set_source_rgb(.9, .9, .9)
            ctx.stroke()

        # Draw horizontal lines
        for y in range(int(self.root.height_mm), -1, -self.grid_size):
            y_px = y*self.pixels_per_mm_y
            ctx.move_to(0, y_px)
            ctx.line_to(width, y_px)
            ctx.set_source_rgb(.9, .9, .9)
            ctx.stroke()
