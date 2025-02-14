from .driver import Driver
from ..models.path import Path


class NoDeviceDriver(Driver):
    """
    A dummy driver that is used if the user has no machine.
    """
    label = 'No driver'
    subtitle = 'No connection'

    async def connect(self) -> None:
        pass

    async def run(self, path: Path) -> None:
        pass

    async def move_to(self, pos_x, pos_y) -> None:
        pass
