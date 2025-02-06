from .modifier import Modifier
from rayforge.util.cairoutil import convert_surface_to_greyscale

class ToGrayscale(Modifier):
    """
    Removes colors from input surface.
    """
    def run(self, workstep, surface, pixels_per_mm, ymax):
        convert_surface_to_greyscale(surface)
