from abc import ABC, abstractmethod


class Processor(ABC):
    """
    Any process that operates on WorkPieces.
    - workstep: the WorkStep that the process is a part of
    - surface: an input surface. Can be manipulated in-place,
      or alternatively a new surface may be returned.
    - pixels_per_mm: tuple: pixels_per_mm_x, pixels_per_mm_y
    - ymax: machine max in y direction
    """
    @staticmethod
    @abstractmethod
    def process(workstep, surface, pixels_per_mm, ymax):
        pass
