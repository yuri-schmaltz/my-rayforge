from abc import ABC, abstractmethod
from ..models.ops import Ops
from ..models.machine import Machine


class OpsEncoder(ABC):
    """
    Encodes Ops while respecting embedded state commands.
    Encoding Ops means: Converting it to an output format.
    Output cut be an image (a cairo surface), a G-code string,
    or any other machine format.
    Maintains context during encoding (current color, power, etc.).
    """
    @abstractmethod
    def encode(self,
               pos: Ops,
               machine: Machine) -> object:
        pass
