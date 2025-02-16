from .driver import Driver
from ..models.ops import Ops


class NoDeviceDriver(Driver):
    """
    A dummy driver that is used if the user has no machine.
    """
    label = 'No driver'
    subtitle = 'No connection'

    async def connect(self) -> None:
        pass

    async def run(self, ops: Ops) -> None:
        pass

    async def set_hold(self, hold: bool = True) -> None:
        pass

    async def cancel(self) -> None:
        pass

    async def home(self) -> None:
        pass

    async def move_to(self, pos_x, pos_y) -> None:
        pass
