import gi

gi.require_version("Gtk", "4.0")
from gi.repository import Gtk, Gdk  # noqa: E402

css = """
.group-view {
    border-radius: 8px;
    background-color: #ffffff;
    box-shadow: 0 6px 6px rgba(0, 0, 0, 0.2);
    margin: 6px 12px 6px 12px;
}

.group-view:hover {
    box-shadow: 0 10px 10px rgba(0, 0, 0, 0.2);
}

.group-title {
    font-size: 1.2em;
    font-weight: bold;
    color: #333;
}

.group-subtitle {
    font-size: 0.9em;
    color: #666;
}

.group-icon-button {
    background-color: transparent;
    border: none;
    border-radius: 12px;
    min-width: 24px;
    min-height: 24px;
    padding: 6px;
}

.group-icon-button:hover {
    background-color: #eee;
}

.group-icon-button:active {
    background-color: #ddd;
}

.group-view > box > box:last-child {
    padding: 12px;
}
"""


class GroupBox(Gtk.Box):
    def __init__(self, title, subtitle, icon_name=None):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=0)

        # Rounded corners and "Material Design" styling (basic implementation)
        self.set_css_classes(["group-view"])  # Use CSS for styling

        # Add box for header, subtitle and icon
        header_hbox = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL,
                              spacing=6)
        header_hbox.set_margin_start(12)
        header_hbox.set_margin_end(12)
        header_hbox.set_margin_top(12)
        header_hbox.set_margin_bottom(6)
        header_hbox.set_halign(Gtk.Align.FILL)
        self.append(header_hbox)

        # Header Box (title, subtitle)
        header_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        header_box.set_hexpand(True)
        header_box.set_valign(Gtk.Align.CENTER)
        self.title_label = Gtk.Label(label=title, halign=Gtk.Align.START)
        self.title_label.set_css_classes(["group-title"])
        self.subtitle_label = Gtk.Label(label=subtitle, halign=Gtk.Align.START)
        self.subtitle_label.set_css_classes(["group-subtitle"])
        header_box.append(self.title_label)
        header_box.append(self.subtitle_label)
        header_hbox.append(header_box)

        # Add icon
        if icon_name:
            icon = Gtk.Image.new_from_icon_name(icon_name)
            self.button = Gtk.Button()
            self.button.set_child(icon)
            self.button.set_css_classes(["group-icon-button"])
            self.button.set_valign(Gtk.Align.CENTER)
            header_hbox.append(self.button)

        # Child widget area
        self.child_area = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.append(self.child_area)
        self.set_hexpand(True)
        self.set_vexpand(True)
        self.apply_css()

    def apply_css(self):
        provider = Gtk.CssProvider()
        provider.load_from_data(css.encode())
        Gtk.StyleContext.add_provider_for_display(
            Gdk.Display.get_default(),
            provider,
            Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
        )

    def add_child(self, widget):
        self.child_area.append(widget)


if __name__ == "__main__":
    class GroupWindow(Gtk.ApplicationWindow):
        def __init__(self, **kwargs):
            super().__init__(**kwargs)

            group_widget = GroupBox(title="My Group",
                                    subtitle="A subtitle for the group",
                                    icon_name="help-symbolic")
            self.set_child(group_widget)
            self.set_default_size(300, 200)

            label = Gtk.Label(label="This is the child widget.")
            group_widget.add_child(label)

    def on_activate(app):
        win = GroupWindow(application=app)
        win.present()

    app = Gtk.Application(application_id="org.example.groupviewexample")
    app.connect('activate', on_activate)
    app.run()
