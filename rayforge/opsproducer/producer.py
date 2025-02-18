from abc import ABC, abstractmethod
from ..models.ops import Ops


class OpsProducer(ABC):
    """
    Given a Cairo surface, an OpsProducer outputs an Ops object.
    Examples may include:

    - Tracing a bitmap to produce a path (Ops object).
    - Reading vector data from an image to turn it into Ops.
    """
    @abstractmethod
    def run(self, machine, laser, surface, pixels_per_mm) -> Ops:
        pass
