from .driver import Driver


class NoDeviceDriver(Driver):
    """
    A dummy driver that is used if the user has no machine.
    """
    async def connect(self) -> None:
        pass

    async def send(self, data: bytes) -> None:
        pass
