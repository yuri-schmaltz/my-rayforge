import asyncio
from abc import ABC, abstractmethod
from enum import Enum
from typing import Callable, Optional, Any
from blinker import Signal


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

    def __init__(self):
        """
        Initialize transport with callbacks and notification handler.
        
        Signals:
            received: Function to handle received data
            status_changed: Function to handle connection status changes
        """
        self.received = Signal()
        self.status_changed = Signal()

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
