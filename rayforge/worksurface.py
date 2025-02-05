from __future__ import annotations
import cairo
from dataclasses import dataclass, field
from canvas import Canvas, CanvasElement
from pathdom import PathDOM
from render import Renderer, SVGRenderer, PNGRenderer
from processor import Processor, MakeTransparent, ToGrayscale, OutlineTracer
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


@dataclass
class WorkAreaItem(CanvasElement):
    renderer: Renderer = None
    data: object = None

    def __post_init__(self):
        if self.renderer is None:
            raise TypeError("__init__ missing 1 required argument: 'renderer'")
        if self.data is None:
            raise TypeError("__init__ missing 1 required argument: 'data'")

    def render(self):
        assert self.surface is not None
        width, height = self.size_px()
        surface = self.renderer.render_item(self, width, height)
        if not surface:
            return self.surface  # we assume surface was changed in-place
        self.surface = _copy_surface(surface, self.surface, width, height)
        return self.surface


@dataclass
class Group(CanvasElement):
    processors: list[Processor] = field(default_factory=lambda: [
        MakeTransparent,
        ToGrayscale,
        OutlineTracer
    ])
    pathdom: PathDOM = PathDOM()
    description: str = 'A group of items to process'

    def render(self):
        super().render()

        # Run the processors.
        width, height = self.size_px()
        self.pathdom.clear()
        for processor in self.processors:
            # The processor can *optionally* return the result on a
            # new surface, in which case we copy it to the existing
            # one (or replace it if it has the same size).
            # If no surface was returned, we assume that the surface
            # was changed in-place, so we can just continue.
            surface = processor.process(self)
            if not surface:
                continue
            self.surface = _copy_surface(surface,
                                         self.surface,
                                         width,
                                         height)

        # Render the processed result.
        canvas = self.get_canvas()
        self.pathdom.render(self.surface,
                            *self.get_pixels_per_mm(),
                            canvas.root.height_mm)

        return self.surface


class WorkSurface(Canvas):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.groups = [Group("default",
                             *self.root.rect(),
                             selectable=False)]
        self.add(self.groups[0])
        self.aspect_ratio = self.root.width_mm/self.root.height_mm
        self.grid_size = 10  # in mm

    def add_svg(self, name, data):
        """
        Add a new item from an SVG (XML as binary string).
        """
        self._add_item(name, SVGRenderer, data)

    def add_png(self, name, data):
        """
        Add a new item from a PNG image (binary string).
        """
        self._add_item(name, PNGRenderer, data)

    def _add_item(self, name, renderer, data):
        data = renderer.prepare(data)
        aspect_ratio = renderer.get_aspect_ratio(data)
        width_mm, height_mm = self._get_default_size_mm(aspect_ratio)
        item = WorkAreaItem(name,
                            self.root.width_mm/2-width_mm/2,
                            self.root.height_mm/2-height_mm/2,
                            width_mm,
                            height_mm,
                            renderer=renderer,
                            data=data)
        self.groups[0].add(item)
        self.queue_draw()

    def _get_default_size_mm(self, aspect_ratio):
        width_mm = self.root.width_mm
        height_mm = width_mm/aspect_ratio
        if height_mm > self.root.height_mm:
            height_mm = self.root.height_mm
            width_mm = height_mm*aspect_ratio
        return width_mm, height_mm

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
