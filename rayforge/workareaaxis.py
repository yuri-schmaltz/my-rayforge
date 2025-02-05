import gi
from workarea import WorkAreaWidget
from axiswidget import AxisWidget

gi.require_version('Gtk', '4.0')
from gi.repository import Gtk  # noqa: E402


class WorkAreaWithAxis(Gtk.Grid):
    def __init__(self, width_mm, height_mm, **kwargs):
        super().__init__(**kwargs)
        self.axis_thickness = 25

        # Create a work area to display the image and paths
        ratio = width_mm/height_mm
        self.workarea = WorkAreaWidget(width_mm=width_mm, height_mm=height_mm)
        self.workarea.set_hexpand(True)
        self.workarea.set_vexpand(True)
        self.workarea.set_halign(Gtk.Align.FILL)
        self.workarea.set_valign(Gtk.Align.FILL)
        self.attach(self.workarea, 1, 0, 1, 1)

        # Add the X axis
        axis = AxisWidget(width_mm,
                          thickness=self.axis_thickness,
                          orientation=Gtk.Orientation.HORIZONTAL)
        self.attach(axis, 1, 1, 1, 1)

        # Add the Y axis
        axis = AxisWidget(height_mm,
                          thickness=self.axis_thickness,
                          orientation=Gtk.Orientation.VERTICAL)
        self.attach(axis, 0, 0, 1, 1)
