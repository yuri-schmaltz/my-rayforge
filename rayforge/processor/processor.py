from abc import ABC, abstractmethod


class Processor(ABC):
    """
    Any process that operates on WorkPieces.
    """
    @staticmethod
    @abstractmethod
    def process(group):
        pass
