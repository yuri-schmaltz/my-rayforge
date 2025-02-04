from abc import ABC, abstractmethod


class Processor(ABC):
    """
    Any process that operates on WorkAreaItems.
    """
    @staticmethod
    @abstractmethod
    def process(group):
        pass
