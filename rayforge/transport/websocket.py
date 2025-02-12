import asyncio
import websockets
from typing import Callable, Optional
from websockets.exceptions import ConnectionClosed
from .transport import Transport, Status


class WebSocketTransport(Transport):
    """
    WebSocket transport with robust state management.
    """

    def __init__(
        self,
        uri: str,
        receive_callback: Optional[Callable[[bytes], None]] = None,
        status_callback: Optional[Callable[[bool], None]] = None,
        notifier: Optional[Callable[[Callable, ...], None]] = None,
    ):
        super().__init__(receive_callback, status_callback, notifier)
        self.uri = uri
        self._websocket: Optional[websockets.WebSocketClientProtocol] = None
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
                # Validate connection object type
                self._notify_status(Status.CONNECTING)
                self._websocket = await websockets.connect(self.uri)
                self._notify_status(Status.CONNECTED)
                self._receive_task = asyncio.create_task(self._receive_loop())
                await self._receive_task
                self._notify_status(Status.IDLE)
            except (asyncio.CancelledError, ConnectionClosed):
                pass
            except Exception as e:
                self._notify_status(Status.ERROR, str(e))
            finally:
                await self._safe_close()
                if self._running:
                    self._notify_status(Status.SLEEPING)
                    await asyncio.sleep(self._reconnect_interval)

    async def disconnect(self) -> None:
        """
        Terminate connection immediately.
        """
        self._notify_status(Status.CLOSING)
        async with self._lock:
            if not self._running:
                return
            self._running = False
            if self._receive_task:
                self._receive_task.cancel()
            await self._safe_close()
        self._notify_status(Status.DISCONNECTED)

    async def send(self, data: bytes) -> None:
        """
        Send data through active connection.
        """
        if self._websocket is None:
            raise ConnectionError("Not connected")
        try:
            await self._websocket.send(data)
        except ConnectionClosed:
            await self._handle_disconnect()

    async def _receive_loop(self) -> None:
        """
        Receive messages with proper state checks.
        """
        try:
            async for message in self._websocket:
                if isinstance(message, bytes):
                    self._notify_receive(message)
        except ConnectionClosed:
            pass
        except Exception as e:
            self._notify_status(Status.ERROR, str(e))

    async def _safe_close(self) -> None:
        """
        Safely close connection with state cleanup.
        """
        if self._websocket is not None:
            try:
                await self._websocket.close()
            except Exception as e:
                self._notify_status(Status.ERROR, str(e))
            finally:
                self._websocket = None

    async def _handle_disconnect(self) -> None:
        """
        Handle unexpected disconnection.
        """
        self._notify_status(Status.CLOSING)
        async with self._lock:
            if self._running:
                await self._safe_close()
        self._notify_status(Status.DISCONNECTED)
