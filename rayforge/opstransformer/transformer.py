from abc import ABC, abstractmethod
from ..models.ops import Ops


class OpsTransformer(ABC):
    """
    Transforms an Ops object in-place.
    Examples may include:

    - Applying travel path optimizations
    - Applying arc welding
    """
    @abstractmethod
    def run(self, pos: Ops) -> None:
        pass
