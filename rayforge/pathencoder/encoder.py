from abc import ABC, abstractmethod
from ..models.path import Path
from ..models.machine import Machine


class PathEncoder(ABC):
    """
    Encodes a Path while respecting embedded state commands.
    Encoding a path means: Converting it to an output format.
    Output cut be an image (a cairo surface), a G-code string,
    or any other machine format.
    Maintains context during encoding (current color, power, etc.).
    """
    @abstractmethod
    def encode(self,
               path: Path,
               machine: Machine) -> object:
        pass
