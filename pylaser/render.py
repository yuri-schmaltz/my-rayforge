import re
from abc import ABC
from xml.etree import ElementTree as ET
from PIL import Image
import cairosvg
import cairo
import io


def parse_length(s):
    m = re.match(r"([0-9.]+)([a-z%]*)", s)
    if m:
        return float(m.group(1)), m.group(2) or "px"
    return float(s)
    return None, None


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
                                    parent_height=height,
                                    output_height=height)
        return cairo.ImageSurface.create_from_png(io.BytesIO(png_data))

    @classmethod
    def get_margins(cls, data):
        """
        Reliably finding the content width of an SVG is surprisingly hard.
        I tried several modules (svgelements, svg2paths2) and all methods
        failed depending on the content of the SVG.

        So instead I render the SVG to PNG, find the width and height
        of the content in relation to the PNG size, and apply the factor
        agains the viewport size of the SVG to get the actual bounds.
        """
        # Open the image with PIL.
        png_data = cairosvg.svg2png(bytestring=data)
        img = Image.open(io.BytesIO(png_data))

        # If the image has an alpha channel, use it to determine non-
        # transparent pixels.
        if img.mode in ('RGBA', 'LA'):
            bbox = img.split()[-1].getbbox()  # bbox of non-transparent pixels
        else:
            # Otherwise, convert to grayscale and compute bbox.
            bbox = img.convert("L").getbbox()

        # Calculate margin percentages relative to the full image dimensions
        x_min, y_min, x_max, y_max = bbox
        img_w, img_h = img.size
        left_pct = x_min / img_w
        top_pct = y_min / img_h
        right_pct = (img_w - x_max) / img_w
        bottom_pct = (img_h - y_max) / img_h

        return left_pct, top_pct, right_pct, bottom_pct

    @classmethod
    def crop_to_content(cls, data):
        left_pct, top_pct, right_pct, bottom_pct = cls.get_margins(data)

        root = ET.fromstring(data)

        # Adjust viewBox by applying the margin percentages
        viewbox_str = root.get("viewBox")
        if not viewbox_str:
            return  # not sure what to do in this case. bail out
        vb_x, vb_y, vb_w, vb_h = map(float, viewbox_str.split())
        new_x = vb_x + left_pct * vb_w
        new_y = vb_y + top_pct * vb_h
        new_w = vb_w * (1 - left_pct - right_pct)
        new_h = vb_h * (1 - top_pct - bottom_pct)
        root.set("viewBox", f"{new_x} {new_y} {new_w} {new_h}")

        width_str = root.get("width")
        if width_str:
            width_val, unit = parse_length(width_str)
            root.set("width", f"{new_w}{unit}")
        height_str = root.get("height")
        if height_str:
            height_val, unit = parse_length(height_str)
            root.set("height", f"{new_h}{unit}")

        return ET.tostring(root, encoding="unicode")


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
