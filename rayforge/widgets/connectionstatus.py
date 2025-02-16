from gi.repository import Gtk
from typing import Optional
from blinker import Signal
from ..driver.driver import driver_mgr, TransportStatus


class ConnectionStatusIconWidget(Gtk.Box):
    def __init__(self):
        super().__init__(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)

        # Create an image widget to display the status icon
        self.status_image = Gtk.Image()
        self.append(self.status_image)

        # Set the initial status
        self.set_status(TransportStatus.DISCONNECTED)

    def set_status(self, status):
        """Update the status icon based on the given status."""
        icon_name = self._get_icon_name_for_status(status)
        self.status_image.set_from_icon_name(icon_name)

    def _get_icon_name_for_status(self, status):
        """Map the status to an appropriate icon name."""
        if status == TransportStatus.UNKNOWN:
            return "network-error-symbolic"
        elif status == TransportStatus.IDLE:
            return "network-idle-symbolic"
        elif status == TransportStatus.CONNECTING:
            return "network-transmit-receive-symbolic"
        elif status == TransportStatus.CONNECTED:
            return "network-wired-symbolic"
        elif status == TransportStatus.ERROR:
            return "network-error-symbolic"
        elif status == TransportStatus.CLOSING:
            return "network-offline-symbolic"
        elif status == TransportStatus.DISCONNECTED:
            return "network-offline-symbolic"
        elif status == TransportStatus.SLEEPING:
            return "network-offline-symbolic"
        else:
            return "network-offline-symbolic"  # Default icon


class ConnectionStatusWidget(Gtk.Button):
    def __init__(self, status=TransportStatus.UNKNOWN):
        super().__init__()
        self.set_has_frame(False)

        box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        self.set_child(box)

        self.label = Gtk.Label()
        box.append(self.label)

        self.icon = ConnectionStatusIconWidget()
        box.append(self.icon)

        self.set_status(status)

    def set_status(self, status):
        self.icon.set_status(status)
        self.label.set_label(status.name)


class ConnectionStatusMonitor(ConnectionStatusWidget):
    def __init__(self):
        self.changed = Signal()
        self.status = TransportStatus.UNKNOWN
        super().__init__()

        driver_mgr.changed.connect(self.on_driver_changed)
        self.on_driver_changed(driver_mgr, driver_mgr.driver)

    def on_driver_changed(self, manager, driver):
        if driver is None:
            return

        # The driver may be new, or it may just have been reconfigured.
        # So we disconnect the signal in case it was already connected.
        driver.connection_status_changed.disconnect(
            self.on_connection_status_changed
        )
        driver.connection_status_changed.connect(
            self.on_connection_status_changed
        )

    def on_connection_status_changed(self,
                                     sender,
                                     status: TransportStatus,
                                     message: Optional[str] = None):
        self.set_status(status)

    def set_status(self, status):
        self.status = status
        super().set_status(status)
        self.changed.send(self)

    def get_status(self):
        return self.status
