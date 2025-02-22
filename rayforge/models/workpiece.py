import cairo
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
        self.renderer: Renderer = None
        self.surface: cairo.Surface = None

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

    def render(self, width: int, height: int, force: bool = False):
        """
        width/height are in pixels
        """
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
