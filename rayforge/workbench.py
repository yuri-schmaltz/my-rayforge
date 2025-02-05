import gi
from worksurface import WorkSurface
from axiswidget import AxisWidget

gi.require_version('Gtk', '4.0')
from gi.repository import Gtk  # noqa: E402


class WorkBench(Gtk.Grid):
    def __init__(self, width_mm, height_mm, **kwargs):
        super().__init__(**kwargs)
        self.axis_thickness = 25

        # Create a work area to display the image and paths
        self.surface = WorkSurface(width_mm=width_mm, height_mm=height_mm)
        self.surface.set_hexpand(True)
        self.surface.set_vexpand(True)
        self.surface.set_halign(Gtk.Align.FILL)
        self.surface.set_valign(Gtk.Align.FILL)
        self.attach(self.surface, 1, 0, 1, 1)

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
