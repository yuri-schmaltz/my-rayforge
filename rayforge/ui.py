import os
import argparse
import gi
from models import Doc, WorkStep, WorkPiece
from workbench import WorkBench
from workstepbox import WorkStepBox
from draglist import DragListBox
from gcode import GCodeSerializer
from render import SVGRenderer, PNGRenderer
from rayforge import __version__

gi.require_version('Adw', '1')
gi.require_version('Gtk', '4.0')
from gi.repository import Gtk, Gio, GLib, Adw  # noqa: E402


class MainWindow(Adw.ApplicationWindow):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.set_title("Rayforge")
        self.set_default_size(1000, 750)

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
        app = self.get_application()
        quit_action = Gio.SimpleAction.new("quit", None)
        quit_action.connect("activate", lambda a, p: app.quit())
        self.add_action(quit_action)

        # Create a toolbar
        toolbar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        toolbar.set_margin_bottom(2)
        toolbar.set_margin_top(2)
        toolbar.set_margin_start(12)
        toolbar.set_margin_end(12)
        vbox.append(toolbar)
        open_button = Gtk.Button(icon_name="document-import-symbolic")
        open_button.set_tooltip_text("Import Image")
        open_button.connect("clicked", self.on_open_clicked)
        toolbar.append(open_button)
        generate_button = Gtk.Button(icon_name="document-save-symbolic")
        generate_button.set_tooltip_text("Generate GCode")
        generate_button.connect("clicked", self.on_generate_clicked)
        toolbar.append(generate_button)

        # Create the Paned splitting the window into left and right sections.
        self.paned = Gtk.Paned(orientation=Gtk.Orientation.HORIZONTAL)
        vbox.append(self.paned)

        # Create a work area to display the image and paths
        width_mm = 600  # TODO: load from machine parameter settings
        height_mm = 300
        ratio = width_mm/height_mm
        self.frame = Gtk.AspectFrame(ratio=ratio, obey_child=False)
        self.frame.set_margin_start(12)
        self.frame.set_margin_end(12)
        self.frame.set_hexpand(True)
        self.paned.set_start_child(self.frame)

        self.workbench = WorkBench(width_mm, height_mm)
        self.workbench.set_hexpand(True)
        self.frame.set_child(self.workbench)

        # Add the GroupListWidget
        panel_width = self.get_default_size()[0]*0.35
        self.worksteplistview = DragListBox()
        self.worksteplistview.set_size_request(panel_width, -1)
        self.paned.set_end_child(self.worksteplistview)
        self.paned.set_resize_end_child(False)
        self.paned.set_shrink_end_child(False)

        # Make a default document.
        self.doc = Doc()
        workstep = WorkStep('Step 1: Outline')
        workstep.description = '100% power, feed 200'
        self.doc.add_workstep(workstep)

        self.update_state()

    def update_state(self):
        for workstep in self.doc.worksteps:
            # Add a workstep to the list.
            row = Gtk.ListBoxRow()
            self.worksteplistview.add_row(row)
            workstepbox = WorkStepBox(workstep)
            row.set_child(workstepbox)

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
        workstep = self.doc.worksteps[0]
        gcode = serializer.serialize(workstep.path)
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
        ext = os.path.splitext(filename)[1].lower()
        match ext:
            case '.svg':
                renderer = SVGRenderer()
            case '.png':
                renderer = PNGRenderer()
            case _:
                print(f"unknown extension: {filename}")
                return
        wp = WorkPiece.from_file(filename, renderer)
        workstep = self.doc.worksteps[0]
        workstep.add_workpiece(wp)
        self.workbench.surface.add_workstep(workstep)

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
        self.set_accels_for_action("win.quit", ["<Ctrl>Q"])
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
