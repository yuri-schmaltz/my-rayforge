import asyncio
from abc import ABC, abstractmethod
from enum import Enum
from typing import Callable, Optional, Any


class Status(Enum):
    IDLE = 1
    CONNECTING = 2
    CONNECTED = 3
    ERROR = 4
    CLOSING = 5
    DISCONNECTED = 6
    SLEEPING = 6


class Transport(ABC):
    """
    Abstract base class for asynchronous data transports.
    """

    def __init__(
        self,
        receive_callback: Optional[Callable[[bytes], None]] = None,
        status_callback: Optional[Callable[[Status, str|None], None]] = None,
        notifier: Optional[Callable[[Callable, ...], None]] = None,
    ):
        """
        Initialize transport with callbacks and notification handler.
        
        Args:
            receive_callback: Function to handle received data
            status_callback: Function to handle connection status changes
            notifier: Thread-safe callback executor (cb, *args) -> None
        """
        self.receive_callback = receive_callback
        self.status_callback = status_callback
        self._notifier = notifier or (
            lambda cb, *args: cb(*args) if cb else None
        )

    def _notify_receive(self, *args) -> None:
        if self.receive_callback:
            self._notifier(self.receive_callback, *args)

    def _notify_status(self, status, msg=None) -> None:
        if self.status_callback:
            self._notifier(self.status_callback, status, msg)

    @abstractmethod
    async def connect(self) -> None:
        """
        Establish connection and start data flow.
        """
        pass

    @abstractmethod
    async def disconnect(self) -> None:
        """
        Gracefully terminate connection and cleanup resources.
        """
        pass

    @abstractmethod
    async def send(self, data: bytes) -> None:
        """
        Send binary data through the transport.
        
        Raises:
            ConnectionError: If transport is not connected
        """
        pass
