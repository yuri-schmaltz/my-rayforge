from rayforge.util.cairoutil import make_transparent
from .modifier import Modifier


class MakeTransparent(Modifier):
    """
    Makes white pixels transparent.
    """
    def run(self, workstep, surface, pixels_per_mm, ymax):
        make_transparent(surface)
