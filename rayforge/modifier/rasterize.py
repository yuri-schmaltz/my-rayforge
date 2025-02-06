from .modifier import Modifier


class Rasterizer(Modifier):
    """
    THIS MODIFIER IS WORK IN PROGRESS. IT IS NOT USABLE.
    Generates rastered movements (using only straight lines)
    across filled pixels in the surface.
    """
    def run(self, workstep, surface, pixels_per_mm, ymax):
        pass  # TODO


class Engrave(Modifier):
    """
    THIS MODIFIER IS WORK IN PROGRESS. IT IS NOT USABLE.
    A smarter version of Rasterizer that attempts to find the shortest
    path for engraving.
    """
    def run(self, workstep, surface, pixels_per_mm, ymax):
        pass  # TODO
