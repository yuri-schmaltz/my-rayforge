import cairo
import io
from ..util.cairoutil import make_transparent
from .renderer import Renderer


class PNGRenderer(Renderer):
    label = 'PNG files'
    mime_types = ('image/png',)
    extensions = ('.png',)

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
    def render_workpiece(cls, data, width=None, height=None):
        return cairo.ImageSurface.create_from_png(io.BytesIO(data))
