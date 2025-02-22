import cairo
from typing import Optional
from ..render import Renderer


class WorkPiece:
    """
    A WorkPiece represents a real world work piece, It is usually
    loaded from an image file and serves as input for all other
    operations.
    """
    def __init__(self, name):
        self.name = name
        self.data: bytes = None
        self.renderer: Optional[Renderer] = None
        self.pos: tuple(float, float) = None, None   # in mm
        self.size: tuple(float, float) = None, None  # in mm
        self._renderer_ref_for_pyreverse: Renderer
        self.surface: cairo.Surface = None

    def set_pos(self, x_mm: float, y_mm: float):
        self.pos = float(x_mm), float(y_mm)

    def set_size(self, width_mm: float, height_mm: float):
        self.size = float(width_mm), float(height_mm)

    def get_natural_size(self):
        return self.renderer.get_natural_size(self.data)

    def get_aspect_ratio(self):
        return self.renderer.get_aspect_ratio(self.data)

    @classmethod
    def from_file(cls, filename, renderer):
        wp = cls(filename)
        with open(filename, 'rb') as fp:
            wp.data = renderer.prepare(fp.read())
        wp.renderer = renderer
        return wp

    def render(self,
               pixels_per_mm_x: int,
               pixels_per_mm_y: int,
               force: bool = False):
        """
        width/height are in pixels
        """
        width = self.pos[0] * pixels_per_mm_x
        height = self.pos[1] * pixels_per_mm_y
        if self.surface \
                and self.surface.get_width() == width \
                and self.surface.get_height() == height \
                and not force:
            return self.surface, False
        self.surface = self.renderer.render_workpiece(self.data,
                                                      width,
                                                      height)
        return self.surface, True

    def dump(self, indent=0):
        print("  "*indent, self.name, self.renderer.label)
