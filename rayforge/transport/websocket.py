import asyncio
import websockets
from typing import Optional
from websockets.exceptions import ConnectionClosed
from .transport import Transport, TransportStatus


class WebSocketTransport(Transport):
    """
    WebSocket transport with robust state management.
    """

    def __init__(self, uri: str, origin=None):
        super().__init__()
        self.uri = uri
        self._websocket: Optional[websockets.WebSocketClientProtocol] = None
        self._origin = origin
        self._running = False
        self._reconnect_interval = 5
        self._lock = asyncio.Lock()
        self._receive_task: Optional[asyncio.Task] = None

    async def connect(self) -> None:
        """
        Establish connection with proper state validation.
        """
        async with self._lock:
            if self._running:
                return
            self._running = True

        while self._running:
            try:
                self.status_changed.send(
                    self,
                    status=TransportStatus.CONNECTING
                )
                self._websocket = await websockets.connect(
                    self.uri,
                    origin=self._origin,
                    additional_headers=(
                        ('Connection', 'Upgrade'),
                        ('Upgrade', 'websocket'),
                    )
                )
                self.status_changed.send(
                    self,
                    status=TransportStatus.CONNECTED
                )
                self._receive_task = asyncio.create_task(self._receive_loop())
                await self._receive_task
                self.status_changed.send(self, status=TransportStatus.IDLE)
            except (asyncio.CancelledError, ConnectionClosed):
                pass
            except Exception as e:
                self.status_changed.send(
                    self,
                    status=TransportStatus.ERROR,
                    message=str(e)
                )
            finally:
                await self._safe_close()
                if self._running:
                    self.status_changed.send(
                        self,
                        status=TransportStatus.SLEEPING
                    )
                    await asyncio.sleep(self._reconnect_interval)

    async def disconnect(self) -> None:
        """
        Terminate connection immediately.
        """
        self.status_changed.send(
            self,
            status=TransportStatus.CLOSING
        )
        async with self._lock:
            if not self._running:
                return
            self._running = False
            if self._receive_task:
                self._receive_task.cancel()
            await self._safe_close()
        self.status_changed.send(
            self,
            status=TransportStatus.DISCONNECTED
        )

    async def send(self, data: bytes) -> None:
        """
        Send data through active connection.
        """
        if self._websocket is None:
            raise ConnectionError("Not connected")
        try:
            await self._websocket.send(self, data)
        except ConnectionClosed:
            await self._handle_disconnect()

    async def _receive_loop(self) -> None:
        """
        Receive messages with proper state checks.
        """
        try:
            async for message in self._websocket:
                if isinstance(message, bytes):
                    self.received.send(self, data=message)
        except ConnectionClosed:
            pass
        except Exception as e:
            self.status_changed.send(
                self,
                status=TransportStatus.ERROR,
                message=str(e)
            )

    async def _safe_close(self) -> None:
        """
        Safely close connection with state cleanup.
        """
        if self._websocket is not None:
            try:
                await self._websocket.close()
            except Exception as e:
                self.status_changed.send(
                    self,
                    status=TransportStatus.ERROR,
                    message=str(e)
                )
            finally:
                self._websocket = None

    async def _handle_disconnect(self) -> None:
        """
        Handle unexpected disconnection.
        """
        self.status_changed.send(
            self,
            status=TransportStatus.CLOSING
        )
        async with self._lock:
            if self._running:
                await self._safe_close()
        self.status_changed.send(
            self,
            status=TransportStatus.DISCONNECTED
        )
