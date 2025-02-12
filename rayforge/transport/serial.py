import asyncio
import logging
import serial_asyncio
from typing import Callable, Optional
from .transport import Transport, Status


class SerialTransport(Transport):
    """
    Asynchronous serial port transport.
    """

    def __init__(
        self,
        port: str,
        baudrate: int,
        receive_callback: Optional[Callable[[bytes], None]] = None,
        status_callback: Optional[Callable[[Status, str|None], None]] = None,
        notifier: Optional[Callable[[Callable, ...], None]] = None,
    ):
        """
        Initialize serial transport.
        
        Args:
            port: Device path (e.g., '/dev/ttyUSB0')
            baudrate: Communication speed in bits per second
        """
        super().__init__(receive_callback, status_callback, notifier)
        self.port = port
        self.baudrate = baudrate
        self._reader: Optional[asyncio.StreamReader] = None
        self._writer: Optional[asyncio.StreamWriter] = None
        self._running = False

    async def connect(self) -> None:
        """
        Open serial connection and start reading.
        """
        self._notify_status(Status.CONNECTING)
        self._reader, self._writer = await serial_asyncio.open_serial_connection(
            url=self.port, baudrate=self.baudrate
        )
        self._running = True
        self._notify_status(Status.CONNECTED)
        asyncio.create_task(self._receive_loop())
        self._notify_status(Status.IDLE)

    async def disconnect(self) -> None:
        """
        Close serial connection.
        """
        self._notify_status(Status.CLOSING)
        self._running = False
        if self._writer:
            self._writer.close()
            await self._writer.wait_closed()
        self._notify_status(Status.DISCONNECTED)

    async def send(self, data: bytes) -> None:
        """
        Write data to serial port.
        """
        if not self._writer:
            raise ConnectionError("Serial port not open")
        self._writer.write(data)
        await self._writer.drain()

    async def _receive_loop(self) -> None:
        """
        Continuous data reception loop.
        """
        while self._running and self._reader:
            try:
                data = await self._reader.read(100)
                if data:
                    self._notify_receive(data)
            except Exception as e:
                self._notify_status(Status.ERROR, str(e))
                break
