import cairo
import io
from .renderer import Renderer


class PNGRenderer(Renderer):
    @classmethod
    def get_aspect_ratio(cls, data):
        surface = cairo.ImageSurface.create_from_png(io.BytesIO(data))
        return surface.get_width()/surface.get_height()

    @classmethod
    def render_item(cls, item, width=None, height=None):
        surface = cairo.ImageSurface.create_from_png(io.BytesIO(item.data))
        scaled = cairo.ImageSurface(cairo.FORMAT_ARGB32, width, height)
        ctx = cairo.Context(scaled)
        ctx.scale(width/surface.get_width(), height/surface.get_height())
        ctx.set_source_surface(surface, 0, 0)
        return cairo.ImageSurface.create_from_png(io.BytesIO(data))
