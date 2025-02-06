from __future__ import annotations
import cairo
from dataclasses import dataclass
from canvas import Canvas, CanvasElement
from models import WorkStep, WorkPiece
import gi

gi.require_version('Gtk', '4.0')
from gi.repository import Graphene  # noqa: E402


def _copy_surface(source, target, width, height):
    in_width, in_height = source.get_width(), source.get_height()
    scale_x = width/in_width
    scale_y = height/in_height
    ctx = cairo.Context(target)
    ctx.scale(scale_x, scale_y)
    ctx.set_source_surface(source, 0, 0)
    ctx.paint()
    return target


def _path2surface(path, surface, scale_x, scale_y, ymax):
    # The path is in machine coordinates, i.e. zero point
    # at the bottom left, and units are mm.
    # Since Cairo coordinates put the zero point at the top left, we must
    # subtract Y from the machine's Y axis maximum.
    ctx = cairo.Context(surface)
    ctx.set_source_rgb(1, 0, 1)
    ctx.scale(scale_x, scale_y)

    ctx.set_line_width(1/scale_x)
    for opname, *args in path.paths:
        op = getattr(ctx, opname)
        if opname in ('move_to', 'line_to'):
            args[1] = ymax-args[1]  # zero point correction
        op(*args)
        if opname == 'close_path':
            ctx.stroke()


@dataclass
class WorkPieceElement(CanvasElement):
    """
    WorkPieceElements display WorkPiece objects on the WorkSurface.
    This is the "standard" element used to display workpieces on the
    WorkSurface.
    """

    def render(self):
        assert self.surface is not None
        width, height = self.size_px()
        workpiece = self.data
        renderer = workpiece.renderer
        surface = renderer.render_workpiece(workpiece, width, height)
        if not surface:
            return self.surface  # we assume surface was changed in-place
        self.surface = _copy_surface(surface, self.surface, width, height)
        return self.surface


@dataclass
class WorkStepElement(CanvasElement):
    """
    WorkStepElements display the result of a WorkStep on the
    WorkSurface. WorkSteps produce output such as the laser path,
    but can also include bitmap modifiers such as converting from color
    to grayscale.
    """

    def render(self):
        super().render()

        # Run the modifiers.
        width, height = self.size_px()
        workstep = self.data
        workstep.path.clear()
        for modifier in workstep.modifiers:
            # The modifier can *optionally* return the result on a
            # new surface, in which case we copy it to the existing
            # one (or replace it if it has the same size).
            # If no surface was returned, we assume that the surface
            # was changed in-place, so we can just continue.
            canvas = self.get_canvas()
            ymax = canvas.root.height_mm
            pixels_per_mm = self.get_pixels_per_mm()
            surface = modifier.run(workstep,
                                   self.surface,
                                   pixels_per_mm,
                                   ymax)
            if not surface:
                continue
            self.surface = _copy_surface(surface,
                                         self.surface,
                                         width,
                                         height)

        # Render the modified result.
        canvas = self.get_canvas()
        _path2surface(workstep.path,
                      self.surface,
                      *self.get_pixels_per_mm(),
                      canvas.root.height_mm)

        return self.surface


class WorkSurface(Canvas):
    """
    The WorkSurface displays a grid area with
    WorkPieces and WorkStep results according to real world
    dimensions.
    """
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.aspect_ratio = self.root.width_mm/self.root.height_mm
        self.grid_size = 10  # in mm

    def add_workstep(self, workstep):
        """
        Adds the workstep, but only if it does not yet exist.
        Also adds each of the WorkPieces, but only if they
        do not exist.
        """
        # Add or find the WorkStep.
        we = self.find_workitem(workstep)
        if we is None:
            we = WorkStepElement(*self.root.rect(),
                                 data=workstep,
                                 selectable=False)
            self.add(we)

        # Add any WorkPieces that were not yet added.
        for workpiece in workstep.workpieces:
            if not we.find_by_data(workpiece):
                self.add_workpiece(workpiece, we)

        self.queue_draw()

    def add_workpiece(self, workpiece, parent_elem=None):
        """
        Adds a workpiece. If not parent element is given, it is
        inserted into the root element.
        """
        aspect_ratio = workpiece.get_aspect_ratio()
        we = parent_elem or self.root
        width_mm, height_mm = we.get_max_child_size(aspect_ratio)
        elem = WorkPieceElement(self.root.width_mm/2-width_mm/2,
                                self.root.height_mm/2-height_mm/2,
                                width_mm,
                                height_mm,
                                data=workpiece)
        we.add(elem)
        self.queue_draw()

    def clear(self):
        self.root.clear()

    def find_workitem(self, item):
        """
        Item may be a WorkPiece or a WorkStep. Returns the CanvasElement.
        """
        return self.root.find_by_data(item)

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
        for y in range(0, int(self.root.height_mm)+1, self.grid_size):
            y_px = y*self.pixels_per_mm_y
            ctx.move_to(0, y_px)
            ctx.line_to(width, y_px)
            ctx.set_source_rgb(.9, .9, .9)
            ctx.stroke()
