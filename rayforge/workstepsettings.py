import gi
from blinker import Signal
from .config import config
from .util.adwfix import get_spinrow_int

gi.require_version('Adw', '1')
gi.require_version('Gtk', '4.0')
from gi.repository import Gtk, Adw  # noqa: E402


class WorkStepSettingsDialog(Adw.PreferencesDialog):
    def __init__(self, workstep, **kwargs):
        super().__init__(**kwargs)
        self.workstep = workstep

        # Create a preferences page
        page = Adw.PreferencesPage()
        self.add(page)

        # Create a preferences group
        group = Adw.PreferencesGroup(title="Workstep Settings")
        page.add(group)

        # Add a slider for power
        power_row = Adw.ActionRow(title="Power (%)")
        power_scale = Gtk.Scale(
            orientation=Gtk.Orientation.HORIZONTAL,
            adjustment=Gtk.Adjustment(
                value=workstep.power/workstep.laser.max_power*100,
                upper=100,
                step_increment=1,
                page_increment=10
            ),
            digits=0,  # No decimal places
            draw_value=True  # Show the current value
        )
        power_scale.set_size_request(300, -1)
        power_scale.connect('value-changed', self.on_power_changed)
        power_row.add_suffix(power_scale)
        group.add(power_row)

        # Add a spin row for cut speed
        cut_speed_row = Adw.SpinRow(
            title="Cut Speed (mm/min)",
            subtitle=f"Max: {config.machine.max_cut_speed} mm/min",
            adjustment=Gtk.Adjustment(
                value=workstep.cut_speed,
                lower=0,
                upper=config.machine.max_cut_speed,
                step_increment=1,
                page_increment=100
            )
        )
        cut_speed_row.connect('changed', self.on_cut_speed_changed)
        group.add(cut_speed_row)

        # Add a spin row for travel speed
        travel_speed_row = Adw.SpinRow(
            title="Travel Speed (mm/min)",
            subtitle=f"Max: {config.machine.max_travel_speed} mm/min",
            adjustment=Gtk.Adjustment(
                value=workstep.travel_speed,
                lower=0,
                upper=config.machine.max_travel_speed,
                step_increment=1,
                page_increment=100
            )
        )
        travel_speed_row.connect('changed', self.on_travel_speed_changed)
        group.add(travel_speed_row)

        self.changed = Signal()

    def on_power_changed(self, scale):
        max_power = self.workstep.laser.max_power
        self.workstep.power = max_power/100*scale.get_value()
        self.changed.send(self)

    def on_cut_speed_changed(self, spin_row):
        self.workstep.cut_speed = get_spinrow_int(spin_row)
        self.changed.send(self)

    def on_travel_speed_changed(self, spin_row):
        self.workstep.travel_speed = get_spinrow_int(spin_row)
        self.changed.send(self)
