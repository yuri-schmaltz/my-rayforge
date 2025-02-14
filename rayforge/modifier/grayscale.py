from ..util.cairoutil import convert_surface_to_grayscale
from .modifier import Modifier


class ToGrayscale(Modifier):
    """
    Removes colors from input surface.
    """
    def run(self, workstep, surface, pixels_per_mm, ymax):
        convert_surface_to_grayscale(surface)
