from abc import ABC, abstractmethod
from typing import Optional
from blinker import Signal
from gi.repository import GLib
from dataclasses import dataclass, field
from enum import Enum, auto
from ..transport import TransportStatus
from ..asyncloop import run_async
from ..models.ops import Ops
from ..models.machine import Machine


class DeviceStatus(Enum):
    UNKNOWN = auto()
    IDLE = auto()
    RUN = auto()
    HOLD = auto()
    JOG = auto()
    ALARM = auto()
    DOOR = auto()
    CHECK = auto()
    HOME = auto()
    SLEEP = auto()
    TOOL = auto()
    QUEUE = auto()
    LOCK = auto()
    UNLOCK = auto()
    CYCLE = auto()
    TEST = auto()


@dataclass
class DeviceState:
    status: int = DeviceStatus.UNKNOWN
    machine_pos: tuple[float, float, float] = None, None, None  # x, y, z in mm
    work_pos: tuple[float, float, float] = None, None, None  # x, y, z in mm


def _falsify(func, *args, **kwargs):
    """
    Wrapper for GLib.idle_add, as function must return False, otherwise it
    is automatically rescheduled into the event loop.
    """
    func(*args, **kwargs)
    return False


class Driver(ABC):
    """
    Abstract base class for all drivers.
    All drivers must provide the following methods:

       setup()
       cleanup()
       connect()
       run()
       move_to()

    All drivers provide the following signals:
       log_received: for log messages
       state_changed: emitted when the DeviceState changes
       command_status_changed: to monitor a command that was sent
       connection_status_changed: signals connectivity changes

    All drivers also provide GLib-safe wrappers for the above signals;
    these arte guaranteed to be triggered in the main GLib event loop
    for convenient usage in UI functions.
    """
    label = None
    subtitle = None

    def __init__(self):
        self.log_received_safe = Signal()
        self.state_changed_safe = Signal()
        self.command_status_changed_safe = Signal()
        self.connection_status_changed_safe = Signal()
        self.did_setup = False
        self.state = DeviceState()

    def setup(self):
        """
        The type annotations of this method are used to generate a UI
        for the user! So if your driver requires any UI parameters,
        you should overload this function to ensure that a UI for the
        parameters is generated.

        The method will be invoked once the user has provided the arguments
        in the UI.
        """
        self.did_setup = True

    async def cleanup(self):
        self.did_setup = False

    @abstractmethod
    async def connect(self) -> None:
        """
        Establishes the connection and maintains it. i.e. auto reconnect.
        On errors or lost connection it should continue trying.
        """
        pass

    @abstractmethod
    async def run(self, ops: Ops, machine: Machine) -> None:
        """
        Converts the given Ops into commands for the machine, and executes
        them.
        """
        pass

    @abstractmethod
    async def move_to(self, pos_x: float, pos_y: float) -> None:
        """
        Moves to the given position. Values are given mm.
        """
        pass

    def _log(self, message: str):
        GLib.idle_add(lambda: _falsify(
            self.log_received_safe.send,
            self,
            message=message
        ))

    def _on_state_changed(self):
        print("New state", self.state)
        GLib.idle_add(lambda: _falsify(
            self.state_changed_safe.send,
            self,
            state=self.state
        ))

    def _on_command_status_changed(self,
                                   status: TransportStatus,
                                   message: Optional[str] = None):
        GLib.idle_add(lambda: _falsify(
            self.command_status_changed_safe.send,
            self,
            status=status,
            message=message
        ))

    def _on_connection_status_changed(self,
                                      status: TransportStatus,
                                      message: Optional[str] = None):
        GLib.idle_add(lambda: _falsify(
            self.connection_status_changed_safe.send,
            self,
            status=status,
            message=message
        ))


class DriverManager:
    def __init__(self):
        self.driver = None
        self.changed = Signal()

    async def _assign_driver(self, driver, **args):
        self.driver = driver
        self.changed.send(self, driver=self.driver)
        self.driver.setup(**args)
        await self.driver.connect()

    async def _reconfigure_driver(self, **args):
        await self.driver.cleanup()
        self.changed.send(self, driver=self.driver)
        self.driver.setup(**args)
        await self.driver.connect()

    async def _switch_driver(self, driver, **args):
        await self.driver.cleanup()
        del self.driver
        await self._assign_driver(driver, **args)

    async def select_by_cls(self, driver_cls, **args):
        if self.driver and self.driver.__class__ == driver_cls:
            await self._reconfigure_driver(**args)
        elif self.driver:
            await self._switch_driver(driver_cls(), **args)
        else:
            await self._assign_driver(driver_cls(), **args)


driver_mgr = DriverManager()
