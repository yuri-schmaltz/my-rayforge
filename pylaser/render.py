from abc import ABC
import cairosvg
import cairo
import io


class Renderer(ABC):
    @classmethod
    def render_item(cls, item, width=None, height=None):
        """
        Renders a WorkAreaItem to a Cairo surface.
        """
        pass


class SVGRenderer(Renderer):
    @classmethod
    def get_aspect_ratio(cls, data):
        surface = cls._render_data(data)
        return surface.get_width()/surface.get_height()

    @classmethod
    def render_item(cls, item, width=None, height=None):
        return cls._render_data(item.data, width, height)

    @classmethod
    def _render_data(cls, data, width=None, height=None):
        png_data = cairosvg.svg2png(bytestring=data,
                                    output_width=width,
                                    output_height=height)
        return cairo.ImageSurface.create_from_png(io.BytesIO(png_data))


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
        return cls._render_data(item.data, width, height)

    @classmethod
    def _render_data(cls, data, width=None, height=None):
        return cairo.ImageSurface.create_from_png(io.BytesIO(data))
