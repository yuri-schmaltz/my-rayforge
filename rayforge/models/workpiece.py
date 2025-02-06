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

    def get_aspect_ratio(self):
        return self.renderer.get_aspect_ratio(self.data)

    @classmethod
    def from_file(cls, filename, renderer):
        wp = cls(filename)
        with open(filename, 'rb') as fp:
            wp.data = renderer.prepare(fp.read())
        wp.renderer = renderer
        return wp

    def dump(self, indent=0):
        print("  "*indent, self.name, self.renderer.label)
