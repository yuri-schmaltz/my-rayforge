from typing import Protocol
from abc import abstractmethod


class Renderable(Protocol):
    @abstractmethod
    def render(self,
               pixels_per_mm_x: int,
               pixels_per_mm_y: int,
               force: bool = False):
        raise NotImplementedError
