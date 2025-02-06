import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')
from gi.repository import Gtk, Adw
from .models.machine import LaserHead


class MachineSettingsDialog(Adw.PreferencesDialog):
    def __init__(self, machine, **kwargs):
        super().__init__(**kwargs)
        self.machine = machine

        # Make the dialog resizable
        self.set_size_request(-1, -1)

        # Create the "General" page (first page)
        general_page = Adw.PreferencesPage(title="General", icon_name=None)
        self.add(general_page)

        # Group for Machine Settings
        machine_group = Adw.PreferencesGroup(title="Machine Settings")
        general_page.add(machine_group)

        # Max Travel Speed
        travel_speed_adjustment = Gtk.Adjustment(
            value=self.machine.max_travel_speed,
            lower=0,
            upper=10000,
            step_increment=1,
            page_increment=10
        )
        self.travel_speed_row = Adw.SpinRow(
            title="Max Travel Speed",
            subtitle="Maximum travel speed in mm/min",
            adjustment=travel_speed_adjustment
        )
        self.travel_speed_row.connect("changed", self.on_travel_speed_changed)
        machine_group.add(self.travel_speed_row)

        # Max Cut Speed
        cut_speed_adjustment = Gtk.Adjustment(
            value=self.machine.max_cut_speed,
            lower=0,
            upper=10000,
            step_increment=1,
            page_increment=10
        )
        self.cut_speed_row = Adw.SpinRow(
            title="Max Cut Speed",
            subtitle="Maximum cutting speed in mm/min",
            adjustment=cut_speed_adjustment
        )
        self.cut_speed_row.connect("changed", self.on_cut_speed_changed)
        machine_group.add(self.cut_speed_row)

        # Dimensions
        dimensions_group = Adw.PreferencesGroup(title="Dimensions")
        general_page.add(dimensions_group)

        width_adjustment = Gtk.Adjustment(
            value=self.machine.dimensions[0],
            lower=20,
            upper=10000,
            step_increment=1,
            page_increment=10
        )
        self.width_row = Adw.SpinRow(
            title="Width",
            subtitle="Width of the machine in mm",
            adjustment=width_adjustment
        )
        self.width_row.connect("changed", self.on_width_changed)
        dimensions_group.add(self.width_row)

        height_adjustment = Gtk.Adjustment(
            value=self.machine.dimensions[1],
            lower=20,
            upper=10000,
            step_increment=1,
            page_increment=10
        )
        self.height_row = Adw.SpinRow(
            title="Height",
            subtitle="Height of the machine in mm",
            adjustment=height_adjustment
        )
        self.height_row.connect("changed", self.on_height_changed)
        dimensions_group.add(self.height_row)

        # Create the "GCode" page
        gcode_page = Adw.PreferencesPage(title="GCode", icon_name=None)
        self.add(gcode_page)

        # Preamble
        preamble_group = Adw.PreferencesGroup(title="Preamble")
        gcode_page.add(preamble_group)
        self.preamble_entry = Gtk.TextView()
        self.preamble_entry.set_size_request(300, 100)
        self.preamble_entry.get_buffer().set_text(
            "\n".join(self.machine.preamble)
        )
        preamble_group.add(self.preamble_entry)

        # Connect the preamble text buffer's "changed" signal
        self.preamble_entry.get_buffer().connect(
            "changed", self.on_preamble_changed
        )

        # Postscript
        postscript_group = Adw.PreferencesGroup(title="Postscript")
        gcode_page.add(postscript_group)
        self.postscript_entry = Gtk.TextView()
        self.postscript_entry.set_size_request(300, 100)
        self.postscript_entry.get_buffer().set_text(
            "\n".join(self.machine.postscript)
        )
        postscript_group.add(self.postscript_entry)

        # Connect the postscript text buffer's "changed" signal
        self.postscript_entry.get_buffer().connect(
            "changed", self.on_postscript_changed
        )

        # Create the "Laser Heads" page
        laserhead_page = Adw.PreferencesPage(title="Laser Heads", icon_name=None)
        self.add(laserhead_page)

        # List of LaserHeads
        laserhead_list_group = Adw.PreferencesGroup(title="Laser Heads")
        laserhead_page.add(laserhead_list_group)
        self.laserhead_list = Gtk.ListBox()
        self.laserhead_list.set_selection_mode(Gtk.SelectionMode.SINGLE)
        self.laserhead_list.set_show_separators(True)  # Add separators
        laserhead_list_group.add(self.laserhead_list)

        # Add and Remove buttons (right-aligned)
        button_box = Gtk.Box(
            orientation=Gtk.Orientation.HORIZONTAL,
            spacing=5,
            halign=Gtk.Align.END
        )
        add_button = Gtk.Button(icon_name="list-add-symbolic")
        add_button.connect("clicked", self.on_add_laserhead)
        remove_button = Gtk.Button(icon_name="list-remove-symbolic")
        remove_button.connect("clicked", self.on_remove_laserhead)
        button_box.append(add_button)
        button_box.append(remove_button)
        laserhead_list_group.add(button_box)

        # Configuration panel for the selected LaserHead
        self.laserhead_config_group = Adw.PreferencesGroup(
            title="Laser Head Configuration"
        )
        laserhead_page.add(self.laserhead_config_group)
        max_power_adjustment = Gtk.Adjustment(
            value=0,
            lower=0,
            upper=10000,
            step_increment=1,
            page_increment=10
        )
        self.max_power_row = Adw.SpinRow(
            title="Max Power",
            subtitle="Maximum power in W",
            adjustment=max_power_adjustment
        )
        self.max_power_row.connect("changed", self.on_max_power_changed)
        self.laserhead_config_group.add(self.max_power_row)

        # Populate the list with existing LaserHeads
        self.populate_laserhead_list()

        # Connect signals
        self.laserhead_list.connect("row-selected", self.on_laserhead_selected)

    def populate_laserhead_list(self):
        """Populate the list of LaserHeads."""
        for head in self.machine.heads:
            row = Adw.ActionRow(title=f"LaserHead (Max Power: {head.max_power} W)")
            row.set_margin_top(5)
            row.set_margin_bottom(5)
            self.laserhead_list.append(row)

    def on_add_laserhead(self, button):
        """Add a new LaserHead to the machine."""
        new_head = LaserHead()
        self.machine.add_head(new_head)
        row = Adw.ActionRow(title=f"LaserHead (Max Power: {new_head.max_power} W)")
        row.set_margin_top(5)
        row.set_margin_bottom(5)
        self.laserhead_list.append(row)
        self.laserhead_list.select_row(row)

    def on_remove_laserhead(self, button):
        """Remove the selected LaserHead from the machine."""
        selected_row = self.laserhead_list.get_selected_row()
        if selected_row:
            index = selected_row.get_index()
            self.machine.heads.pop(index)
            self.laserhead_list.remove(selected_row)

    def on_laserhead_selected(self, listbox, row):
        """Update the configuration panel when a LaserHead is selected."""
        if row is not None:
            index = row.get_index()
            selected_head = self.machine.heads[index]
            self.max_power_row.set_value(selected_head.max_power)

    def on_max_power_changed(self, spinrow):
        """Update the max power of the selected LaserHead."""
        selected_row = self.laserhead_list.get_selected_row()
        if selected_row:
            index = selected_row.get_index()
            self.machine.heads[index].max_power = spinrow.get_value()
            self.update_laserhead_list()

    def update_laserhead_list(self):
        """Update the labels in the LaserHead list."""
        for i, row in enumerate(self.laserhead_list):
            head = self.machine.heads[i]
            row.set_title(f"LaserHead (Max Power: {head.max_power} W)")

    def on_preamble_changed(self, buffer):
        """Update the preamble when the text changes."""
        text = buffer.get_text(
            buffer.get_start_iter(),
            buffer.get_end_iter(),
            True
        )
        self.machine.set_preamble(text.splitlines())

    def on_postscript_changed(self, buffer):
        """Update the postscript when the text changes."""
        text = buffer.get_text(
            buffer.get_start_iter(),
            buffer.get_end_iter(),
            True
        )
        self.machine.set_postscript(text.splitlines())

    def on_travel_speed_changed(self, spinrow):
        """Update the max travel speed when the value changes."""
        self.machine.set_max_travel_speed(spinrow.get_value())

    def on_cut_speed_changed(self, spinrow):
        """Update the max cut speed when the value changes."""
        self.machine.set_max_cut_speed(spinrow.get_value())

    def on_width_changed(self, spinrow):
        """Update the width when the value changes."""
        width = spinrow.get_value()
        height = self.machine.dimensions[1]
        self.machine.set_dimensions(width, height)

    def on_height_changed(self, spinrow):
        """Update the height when the value changes."""
        width = self.machine.dimensions[0]
        height = spinrow.get_value()
        self.machine.set_dimensions(width, height)
