import cairo
import io
from pylaser.processor.transparency import make_transparent
from .renderer import Renderer


class PNGRenderer(Renderer):
    @classmethod
    def prepare(cls, data):
        stream = io.BytesIO(data)
        surface = cairo.ImageSurface.create_from_png(stream)
        make_transparent(surface)
        stream.seek(0)
        surface.write_to_png(stream)
        return stream.getvalue()

    @classmethod
    def get_aspect_ratio(cls, data):
        surface = cairo.ImageSurface.create_from_png(io.BytesIO(data))
        return surface.get_width()/surface.get_height()

    @classmethod
    def render_item(cls, item, width=None, height=None):
        return cairo.ImageSurface.create_from_png(io.BytesIO(item.data))
