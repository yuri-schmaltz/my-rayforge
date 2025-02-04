import os
import argparse
import gi
from workarea import WorkAreaWidget
from gcode import GCodeSerializer
from rayforge import __version__

gi.require_version('Adw', '1')
gi.require_version('Gtk', '4.0')
from gi.repository import Gtk, Gio, GLib, Adw  # noqa: E402


class MainWindow(Adw.ApplicationWindow):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.set_title("Rayforge")
        self.set_default_size(1000, 700)

        # Create the main vbox
        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        self.set_content(vbox)

        # Show the application header bar with hamburger menu
        header_bar = Adw.HeaderBar()
        vbox.append(header_bar)

        # Create a menu
        menu_button = Gtk.MenuButton()
        menu_model = Gio.Menu()
        menu_model.append("About", "win.about")
        menu_model.append("Quit", "win.quit")
        menu_button.set_menu_model(menu_model)
        header_bar.pack_end(menu_button)

        # Add the "about" action
        about_action = Gio.SimpleAction.new("about", None)
        about_action.connect("activate", self.show_about_dialog)
        self.add_action(about_action)

        # Add the "quit" action
        quit_action = Gio.SimpleAction.new("quit", None)
        quit_action.connect("activate", lambda a, p: self.quit())
        self.add_action(quit_action)

        # Create a toolbar
        toolbar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        vbox.append(toolbar)
        open_button = Gtk.Button(icon_name="document-import-symbolic")
        open_button.set_tooltip_text("Import Image")
        open_button.connect("clicked", self.on_open_clicked)
        toolbar.append(open_button)
        generate_button = Gtk.Button(icon_name="document-save-symbolic")
        generate_button.set_tooltip_text("Generate GCode")
        generate_button.connect("clicked", self.on_generate_clicked)
        toolbar.append(generate_button)

        # Create a work area to display the image and paths
        self.workarea = WorkAreaWidget(width_mm=200, height_mm=200)
        self.workarea.set_hexpand(True)
        self.workarea.set_vexpand(True)
        vbox.append(self.workarea)

    def on_open_clicked(self, button):
        # Create a file chooser dialog
        dialog = Gtk.FileDialog.new()
        dialog.set_title("Open SVG File")

        # Create a file filter for SVG files
        filter_svg = Gtk.FileFilter()
        filter_svg.set_name("SVG files")
        filter_svg.add_mime_type("image/svg+xml")
        filter_svg.add_mime_type("image/png")

        # Create a Gio.ListModel for the filters
        filters = Gio.ListStore.new(Gtk.FileFilter)
        filters.append(filter_svg)

        # Set the filters for the dialog
        dialog.set_filters(filters)

        # Show the dialog and handle the response
        dialog.open(self, None, self.on_file_dialog_response)

    def on_generate_clicked(self, button):
        serializer = GCodeSerializer()
        group = self.workarea.groups[0]
        group.render()
        gcode = serializer.serialize(group.pathdom)
        print(gcode)

    def on_file_dialog_response(self, dialog, result):
        try:
            # Get the selected file
            file = dialog.open_finish(result)
            if file:
                # Load the SVG file and convert it to a grayscale surface
                file_path = file.get_path()
                self.load_file(file_path)
        except GLib.Error as e:
            print(f"Error opening file: {e.message}")

    def load_file(self, filename):
        with open(filename, 'rb') as fp:
            ext = os.path.splitext(filename)[1].lower()
            match ext:
                case '.svg':
                    self.workarea.add_svg(filename, fp.read())
                case '.png':
                    self.workarea.add_png(filename, fp.read())
                case _:
                    print(f"unknown extension: {filename}")
                    return

    def show_about_dialog(self, action, param):
        about_dialog = Adw.AboutDialog(
            application_name="Rayforge",
            developer_name="Barebaric",
            version=__version__ or 'unknown',
            copyright="© 2025 Samuel Abels",
            website="https://github.com/barebaric/rayforge",
            issue_url="https://github.com/barebaric/rayforge/issues",
            developers=["Samuel Abels"],
            license_type=Gtk.License.MIT_X11
        )
        about_dialog.present()


class MyApp(Adw.Application):
    def __init__(self, args):
        super().__init__(application_id='com.barebaric.Rayforge')
        self.set_accels_for_action("app.quit", ["<Ctrl>Q"])
        self.args = args

    def do_activate(self):
        win = MainWindow(application=self)
        if self.args.filename:
            win.load_file(self.args.filename)
        win.present()


def run():
    parser = argparse.ArgumentParser(
            description="A GCode generator for laser cutters.")
    parser.add_argument("filename",
                        help="Path to the input SVG or image file.",
                        nargs='?')

    args = parser.parse_args()
    app = MyApp(args)
    app.run(None)

if __name__ == '__main__':
    run()
