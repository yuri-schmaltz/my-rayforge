import gi
import asyncio
from datetime import datetime
from locale import getdefaultlocale
from ..driver.driver import driver_mgr, Status

gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')
from gi.repository import Gtk, Adw, GLib, Pango  # noqa: E402


css = """
.terminal {
    font-family: Monospace;
    font-size: 10pt;
}
"""


class MachineView(Adw.Dialog):
    def __init__(self):
        super().__init__()
        self.set_presentation_mode(Adw.DialogPresentationMode.BOTTOM_SHEET)

        # Main container
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        self.set_child(box)

        # WebSocket terminal-like display
        self.terminal = Gtk.TextView()
        self.terminal.set_editable(False)  # Make it read-only
        self.terminal.set_cursor_visible(False)  # Hide the cursor
        self.terminal.set_wrap_mode(Gtk.WrapMode.WORD_CHAR)  # Wrap text
        self.terminal.set_margin_top(12)
        self.terminal.set_margin_bottom(12)
        self.terminal.set_margin_start(12)
        self.terminal.set_margin_end(12)

        # Apply a monospace font using CSS
        css_provider = Gtk.CssProvider()
        css_provider.load_from_data(css)
        self.terminal.get_style_context().add_provider(
            css_provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
        )

        # Wrap the TextView in a ScrolledWindow
        scrolled_window = Gtk.ScrolledWindow()
        scrolled_window.set_min_content_height(400)  # Set a minimum height
        scrolled_window.set_child(self.terminal)
        box.append(scrolled_window)

        # Listen to driver
        driver = driver_mgr.driver
        driver.received_safe.connect(self.on_data_received)
        driver.command_status_changed_safe.connect(
            self.on_command_status_changed
        )
        driver.connection_status_changed_safe.connect(
            self.on_connection_status_changed
        )

        # Make the dialog expand to the full width of the parent window
        self.set_size_request(12000, 200)  # Allow the dialog to expand
        self.set_follows_content_size(True)

    def on_data_received(self, sender, data=None):
        """
        Update terminal display.
        """
        # Get the current timestamp in the user's locale
        timestamp = datetime.now().strftime("%x %X")  # Locale-specific date and time
        formatted_message = f"[{timestamp}] {data}\n"

        # Get the TextBuffer and insert the new message
        text_buffer = self.terminal.get_buffer()
        text_buffer.insert(text_buffer.get_end_iter(), formatted_message)

        # Scroll to the end of the buffer
        self.terminal.scroll_to_iter(text_buffer.get_end_iter(), 0, False, 0, 0)
        return False

    def on_command_status_changed(self, sender, status: Status, message: str|None=None):
        self.send_button.set_sensitive(status)

    def on_connection_status_changed(self, sender, status: Status, message: str|None=None):
        icon = "network-idle-symbolic" \
                if status.CONNECTED \
                else "network-offline-symbolic"
        self.connection_status_icon.set_from_icon_name(icon)
        self.connection_status_label.set_label(status.name)
