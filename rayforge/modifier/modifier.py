class Modifier:
    """
    Modifies a Cairo surface.
    """
    def __init__(self):
        self.label = self.__class__.__name__

    def run(self, surface):
        """
        - workstep: the WorkStep that the process is a part of
        - surface: an input surface. Can be manipulated in-place,
          or alternatively a new surface may be returned.
        - pixels_per_mm: tuple: pixels_per_mm_x, pixels_per_mm_y
        - ymax: machine max in y direction
        """
        pass
