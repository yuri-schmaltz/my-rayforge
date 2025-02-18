from abc import ABC, abstractmethod
from ..models.ops import Ops
from ..models.machine import Machine


class OpsEncoder(ABC):
    """
    Transforms an Ops object into something else.
    Examples:

    - Ops to image (a cairo surface)
    - Ops to a G-code string
    """
    @abstractmethod
    def encode(self, pos: Ops, machine: Machine) -> object:
        pass
