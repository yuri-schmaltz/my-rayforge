import asyncio
from typing import Optional
import aiohttp
from .transport import Transport, Status


class HttpTransport(Transport):
    """
    HTTP transport using persistent connection with auto-reconnect.
    """

    def __init__(self, base_url: str, receive_interval: int = None):
        """
        Initialize HTTP transport.

        Args:
            base_url: Server endpoint URL (schema://host:port)
        """
        super().__init__()
        self.base_url = base_url
        self.session: Optional[aiohttp.ClientSession] = None
        self._running = False
        self._reconnect_interval = 5
        self._receive_interval = receive_interval
        self._connection_task: Optional[asyncio.Task] = None

    async def connect(self) -> None:
        """
        Start connection/reconnection loop.
        """
        self._running = True
        self._connection_task = asyncio.create_task(self._connection_loop())

    async def disconnect(self) -> None:
        """
        Terminate connection and cancel background tasks.
        """
        self._running = False
        if self._connection_task:
            self._connection_task.cancel()
        if self.session:
            await self.session.close()

    async def send(self, data: bytes) -> None:
        """
        Send data to HTTP endpoint via POST request.
        """
        if not self.session:
            raise ConnectionError("Not connected to server")

        try:
            async with self.session.post(
                f"{self.base_url}",
                data=data,
                timeout=aiohttp.ClientTimeout(total=5),
            ) as response:
                if response.status != 200:
                    raise IOError(f"Send failed: {await response.text()}")
        except aiohttp.ClientError as e:
            await self._handle_error(e)

    async def _connection_loop(self) -> None:
        """
        Maintain persistent connection with reconnect logic.
        """
        while self._running:
            try:
                self.status_changed.send(self, status=Status.CONNECTING)
                self.session = aiohttp.ClientSession()
                self.status_changed.send(self, status=Status.CONNECTED)
                await self._receive_loop()
            except aiohttp.ClientError as e:
                await self._handle_error(e)
            finally:
                await self._safe_close_session()
                self.status_changed.send(self, status=Status.DISCONNECTED)

            if self._running:
                await asyncio.sleep(self._reconnect_interval)

    async def _receive_loop(self) -> None:
        """
        Listen for server-sent events from streaming endpoint.
        """
        while self._running and self.session:
            try:
                async with self.session.get(
                    f"{self.base_url}",
                    timeout=aiohttp.ClientTimeout(total=30),
                ) as response:
                    if response.status == 200:
                        data = await response.read()
                        if data:
                            self.received.send(self, data=data)
            except aiohttp.ClientError as e:
                await self._handle_error(e)
                break
            if self._running and self._receive_interval:
                await asyncio.sleep(self._receive_interval)

    async def _handle_error(self, error: Exception) -> None:
        """
        Log errors and update connection status.
        """
        if self._running:
            self.status_changed.send(self,
                                     status=Status.ERROR,
                                     message=str(error))

    async def _safe_close_session(self) -> None:
        """
        Safely close aiohttp session ignoring errors.
        """
        try:
            if self.session and not self.session.closed:
                await self.session.close()
        except Exception as e:
            self.status_changed.send(self,
                                     status=Status.ERROR,
                                     message=str(e))
