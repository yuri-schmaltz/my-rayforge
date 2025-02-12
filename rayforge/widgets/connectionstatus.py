import gi
gi.require_version('Gtk', '4.0')
from gi.repository import Gtk
from ..driver.driver import driver_mgr, Status


class ConnectionStatusIconWidget(Gtk.Box):
    def __init__(self):
        super().__init__(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)

        # Create an image widget to display the status icon
        self.status_image = Gtk.Image()
        self.append(self.status_image)

        # Set the initial status
        self.set_status(Status.DISCONNECTED)

    def set_status(self, status):
        """Update the status icon based on the given status."""
        icon_name = self._get_icon_name_for_status(status)
        self.status_image.set_from_icon_name(icon_name)

    def _get_icon_name_for_status(self, status):
        """Map the status to an appropriate icon name."""
        if status == Status.UNKNOWN:
            return "network-error-symbolic"
        elif status == Status.IDLE:
            return "network-idle-symbolic"
        elif status == Status.CONNECTING:
            return "network-transmit-receive-symbolic"
        elif status == Status.CONNECTED:
            return "network-wired-symbolic"
        elif status == Status.ERROR:
            return "network-error-symbolic"
        elif status == Status.CLOSING:
            return "network-offline-symbolic"
        elif status == Status.DISCONNECTED:
            return "network-offline-symbolic"
        elif status == Status.SLEEPING:
            return "network-offline-symbolic"
        else:
            return "network-offline-symbolic"  # Default icon


class ConnectionStatusWidget(Gtk.Button):
    def __init__(self, status=Status.UNKNOWN):
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
        super().__init__()

        driver_mgr.changed.connect(self.on_driver_changed)
        self.on_driver_changed(driver_mgr, driver_mgr.driver)

    def on_driver_changed(self, manager, driver):
        if driver is None:
            return
        driver.connection_status_changed_safe.connect(
            self.on_connection_status_changed
        )

    def on_connection_status_changed(self,
                                     sender,
                                     status: Status,
                                     message: str|None=None):
        self.set_status(status)
