from typing import Callable, Optional
from ..transport import HttpTransport, WebSocketTransport, Status
from .driver import Driver


class ICubeDriver(Driver):
    """
    Handles Sparkfun iCube via HTTP+WebSocket
    """
    
    def __init__(self, host: str):
        super().__init__()

        # Initialize transports
        self.http = HttpTransport(f'http://{host}:9999')
        self.http.received.connect(self.on_http_data_received)
        self.http.status_changed.connect(self.on_http_status_changed)

        self.websocket = WebSocketTransport(f'ws://{host}:9991')
        self.websocket.received.connect(self.on_websocket_data_received)
        self.websocket.status_changed.connect(self.on_websocket_status_changed)

    async def connect(self):
        await self.http.connect()
        await self.websocket.connect()

    async def send(self, data: bytes) -> None:
        # TODO: input should be Path, and we should send GCode
        await self.http.send(self, data)

    def on_http_data_received(self, sender, data: bytes):
        self.received.send(self, data=data)

    def on_http_status_changed(self, sender, status: Status, message: str|None=None):
        self.command_status_changed.send(self,
                                         status=status,
                                         message=message)

    def on_websocket_data_received(self, sender, data: bytes):
        #TODO: Parse message into something readable
        self.received.send(self, data=data)

    def on_websocket_status_changed(self, sender, status: Status, message: str|None=None):
        self.connection_status_changed.send(self,
                                            status=status,
                                            message=message)
