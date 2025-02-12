from abc import ABC, abstractmethod
from typing import Callable, Optional
from functools import partial
from blinker import Signal
from gi.repository import GLib  # noqa: E402
from ..transport import Status


def _falsify(func, *args, **kwargs):
    """
    Wrapper for GLib.idle_add, as function must return False, otherwise it
    is automatically rescheduled into the event loop.
    """
    func(*args, **kwargs)
    return False


class Driver:
    """
    Abstract base class for all drivers.
    All drivers must provide the following methods:
       connect()
       send()

    All drivers provide the following signals:
       received: whenever data was received
       command_status_changed: to monitor a command that was sent
       connection_status_changed: signals connectivity changes

    All drivers also provide GLib-safe wrappers for the above signals;
    these arte guaranteed to be triggered in the main GLib event loop
    for convenient usage in UI functions.
    """
    
    def __init__(self):
        self.received = Signal()
        self.command_status_changed = Signal()
        self.connection_status_changed = Signal()

        self.received_safe = Signal()
        self.command_status_changed_safe = Signal()
        self.connection_status_changed_safe = Signal()

        self.received.connect(self.on_received)
        self.command_status_changed.connect(self.on_command_status_changed)
        self.connection_status_changed.connect(
            self.on_connection_status_changed
        )

    @abstractmethod
    async def connect(self) -> None:
        pass

    @abstractmethod
    async def send(self, data: bytes) -> None:
        pass

    def on_received(self, sender, data: bytes):
        GLib.idle_add(lambda: _falsify(
            self.received_safe.send,
            sender,
            data=data
        ))

    def on_command_status_changed(self,
                                  sender,
                                  status: Status,
                                  message: str|None=None):
        GLib.idle_add(lambda: _falsify(
            self.command_status_changed_safe.send,
            self,
            status=status,
            message=message
        ))

    def on_connection_status_changed(self,
                                     sender,
                                     status: Status,
                                     message: str|None=None):
        GLib.idle_add(lambda: _falsify(
            self.connection_status_changed_safe.send,
            self,
            status=status,
            message=message
        ))


class DriverManager:
    def __init__(self):
        self.driver = None

    def select(self, driver):
        self.driver = driver


driver_mgr = DriverManager()
