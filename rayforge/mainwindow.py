import mimetypes
import gi
from .config import config
from .util.resources import get_icon_path
from .models.doc import Doc
from .models.workstep import WorkStep
from .models.workpiece import WorkPiece
from .workbench import WorkBench
from .workstepbox import WorkStepBox
from .draglist import DragListBox
from .machinesettings import MachineSettingsDialog
from .gcode import GCodeSerializer
from .render import renderers, renderer_by_mime_type
from . import __version__

gi.require_version('Adw', '1')
gi.require_version('Gtk', '4.0')
from gi.repository import Gtk, Gio, GLib, Gdk, Adw  # noqa: E402


class MainWindow(Adw.ApplicationWindow):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.set_title("Rayforge")

        # Get the primary monitor size
        display = Gdk.Display.get_default()
        monitor = display.get_primary_monitor()
        geometry = monitor.get_geometry()
        self.set_default_size(int(geometry.width*0.6),
                              int(geometry.height*0.6))

        # Define a "window quit" action.
        quit_action = Gio.SimpleAction.new("quit", None)
        quit_action.connect("activate", self.on_quit_action)
        self.add_action(quit_action)

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
        menu_model.append("Preferences", "win.settings")
        menu_button.set_menu_model(menu_model)
        header_bar.pack_end(menu_button)

        # Add the "about" action
        about_action = Gio.SimpleAction.new("about", None)
        about_action.connect("activate", self.show_about_dialog)
        self.add_action(about_action)

        # Add the "quit" action
        app = self.get_application()
        settings_action = Gio.SimpleAction.new("settings", None)
        settings_action.connect("activate", self.show_machine_settings)
        self.add_action(settings_action)

        # Create a toolbar
        toolbar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        toolbar.set_margin_bottom(2)
        toolbar.set_margin_top(2)
        toolbar.set_margin_start(12)
        toolbar.set_margin_end(12)
        vbox.append(toolbar)

        icon = Gtk.Image.new_from_file(get_icon_path('open'))
        open_button = Gtk.Button()
        open_button.set_child(icon)
        open_button.set_tooltip_text("Import Image")
        open_button.connect("clicked", self.on_open_clicked)
        toolbar.append(open_button)

        icon = Gtk.Image.new_from_file(get_icon_path('send'))
        self.export_button = Gtk.Button()
        self.export_button.set_child(icon)
        self.export_button.set_tooltip_text("Generate GCode")
        self.export_button.connect("clicked", self.on_export_clicked)
        toolbar.append(self.export_button)

        # Create the Paned splitting the window into left and right sections.
        self.paned = Gtk.Paned(orientation=Gtk.Orientation.HORIZONTAL)
        vbox.append(self.paned)

        # Create a work area to display the image and paths
        width_mm, height_mm = config.machine.dimensions
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
        self.worksteplistview = DragListBox()
        self.worksteplistview.set_size_request(350, -1)
        self.paned.set_end_child(self.worksteplistview)
        self.paned.set_resize_end_child(False)
        self.paned.set_shrink_end_child(False)

        # Make a default document.
        self.doc = Doc()
        workstep = WorkStep('Step 1: Outline')
        self.doc.add_workstep(workstep)

        self.update_state()
        config.changed.connect(self.on_config_changed)

    def on_config_changed(self, sender, **kwargs):
        self.workbench.set_size(*config.machine.dimensions)
        width_mm, height_mm = config.machine.dimensions
        ratio = width_mm/height_mm
        self.frame.set_ratio(ratio)

    def update_state(self):
        self.workbench.update(self.doc)

        # Add worksteps to the side panel.
        self.worksteplistview.remove_all()
        for workstep in self.doc.worksteps:
            row = Gtk.ListBoxRow()
            self.worksteplistview.add_row(row)
            workstepbox = WorkStepBox(workstep)
            row.set_child(workstepbox)

        # Update button states.
        self.export_button.set_sensitive(self.doc.has_workpiece())

    def on_quit_action(self, action, parameter):
        self.close()

    def on_open_clicked(self, button):
        # Create a file chooser dialog
        dialog = Gtk.FileDialog.new()
        dialog.set_title("Open SVG File")

        # Create a Gio.ListModel for the filters
        filter_list = Gio.ListStore.new(Gtk.FileFilter)
        all_supported = Gtk.FileFilter()
        all_supported.set_name("All supported")
        for renderer in renderers:
            file_filter = Gtk.FileFilter()
            file_filter.set_name(renderer.label)
            for mime_type in renderer.mime_types:
                file_filter.add_mime_type(mime_type)
                all_supported.add_mime_type(mime_type)
            filter_list.append(file_filter)
        filter_list.append(all_supported)

        # Set the filters for the dialog
        dialog.set_filters(filter_list)
        dialog.set_default_filter(all_supported)

        # Show the dialog and handle the response
        dialog.open(self, None, self.on_file_dialog_response)

    def on_export_clicked(self, button):
        # Create a file chooser dialog for saving the file
        dialog = Gtk.FileDialog.new()
        dialog.set_title("Save G-code File")

        # Set the default file name
        dialog.set_initial_name("output.gcode")

        # Create a Gio.ListModel for the filters
        filter_list = Gio.ListStore.new(Gtk.FileFilter)
        gcode_filter = Gtk.FileFilter()
        gcode_filter.set_name("G-code files")
        gcode_filter.add_mime_type("text/x-gcode")
        filter_list.append(gcode_filter)

        # Set the filters for the dialog
        dialog.set_filters(filter_list)
        dialog.set_default_filter(gcode_filter)

        # Show the dialog and handle the response
        dialog.save(self, None, self.on_save_dialog_response)

    def on_save_dialog_response(self, dialog, result):
        try:
            file = dialog.save_finish(result)
            if not file:
                return
            file_path = file.get_path()

            # Serialize the G-code
            serializer = GCodeSerializer(config.machine)
            workstep = self.doc.worksteps[0]
            gcode = serializer.serialize(workstep)

            # Write the G-code to the file
            with open(file_path, 'w') as f:
                f.write(gcode)
        except GLib.Error as e:
            print(f"Error saving file: {e.message}")

    def on_file_dialog_response(self, dialog, result):
        try:
            # Get the selected file
            file = dialog.open_finish(result)
            if file:
                # Load the SVG file and convert it to a grayscale surface
                file_path = file.get_path()
                file_info = file.query_info(
                    Gio.FILE_ATTRIBUTE_STANDARD_CONTENT_TYPE,
                    Gio.FileQueryInfoFlags.NONE,
                    None
                )
                mime_type = file_info.get_content_type()
                self.load_file(file_path, mime_type)
        except GLib.Error as e:
            print(f"Error opening file: {e.message}")

    def load_file(self, filename, mime_type):
        renderer = renderer_by_mime_type[mime_type]
        wp = WorkPiece.from_file(filename, renderer)
        self.doc.add_workpiece(wp)
        self.update_state()

    def show_about_dialog(self, action, param):
        about_dialog = Adw.AboutDialog(
            application_name="Rayforge",
            application_icon="com.barebaric.rayforge",
            developer_name="Barebaric",
            version=__version__ or 'unknown',
            copyright="© 2025 Samuel Abels",
            website="https://github.com/barebaric/rayforge",
            issue_url="https://github.com/barebaric/rayforge/issues",
            developers=["Samuel Abels"],
            license_type=Gtk.License.MIT_X11
        )
        about_dialog.present()

    def show_machine_settings(self, action, param):
        dialog = MachineSettingsDialog(config.machine)
        dialog.present()
