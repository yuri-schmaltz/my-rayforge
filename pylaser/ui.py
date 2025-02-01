import argparse
import gi
from image import render_svg_to_surface, convert_surface_to_greyscale
from workarea import WorkAreaWidget

gi.require_version('Gtk', '4.0')
from gi.repository import Gtk, Gio, GLib  # noqa: E402


class SVGViewer(Gtk.ApplicationWindow):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.set_title("SVG to Grayscale Bitmap Viewer")
        self.set_default_size(800, 600)

        # Create a button to open the SVG file
        self.open_button = Gtk.Button(label="Open SVG")
        self.open_button.connect("clicked", self.on_open_clicked)

        # Create a work area to display the image and paths
        self.workarea = WorkAreaWidget(width_mm=100, height_mm=100)
        self.workarea.set_vexpand(True)

        # Create a vertical box to hold the button and drawing area
        self.box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        self.box.append(self.open_button)
        self.box.append(self.workarea)

        self.set_child(self.box)

    def on_open_clicked(self, button):
        # Create a file chooser dialog
        dialog = Gtk.FileDialog.new()
        dialog.set_title("Open SVG File")

        # Create a file filter for SVG files
        filter_svg = Gtk.FileFilter()
        filter_svg.set_name("SVG files")
        filter_svg.add_mime_type("image/svg+xml")

        # Create a Gio.ListModel for the filters
        filters = Gio.ListStore.new(Gtk.FileFilter)
        filters.append(filter_svg)

        # Set the filters for the dialog
        dialog.set_filters(filters)

        # Show the dialog and handle the response
        dialog.open(self, None, self.on_file_dialog_response)

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
        surface = render_svg_to_surface(filename)
        surface = convert_surface_to_greyscale(surface)
        self.workarea.add_surface(surface)


class MyApp(Gtk.Application):
    def __init__(self, args):
        super().__init__(application_id='org.example.myapp')
        self.args = args

    def do_activate(self):
        win = SVGViewer(application=self)
        if args.filename:
            win.load_file(args.filename)
        win.present()


parser = argparse.ArgumentParser(
        description="GCode generator for laser cutters.")
parser.add_argument("filename",
                    help="Path to the input SVG or image file.",
                    nargs='?')

if __name__ == '__main__':
    args = parser.parse_args()
    app = MyApp(args)
    app.run(None)
