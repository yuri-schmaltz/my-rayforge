import inspect
from gi.repository import Gtk, Adw
from blinker import Signal
from ..util.adwfix import get_spinrow_int


class DynamicPreferencesGroup(Adw.PreferencesGroup):
    def __init__(self, *args, **kwargs):
        """
        Params is a dict of items as returned by
        inspect.signature.parameters.items()
        """
        super().__init__(*args, **kwargs)
        self.widget_map = {}
        self.data_changed = Signal()

    def clear(self):
        for row in self.widget_map.values():
            self.remove(row)
        self.widget_map = {}

    def create_params(self, params):
        self.clear()

        # Get constructor parameters
        for name, param in params:
            if name == 'self':
                continue

            annotation = param.annotation
            isempty = param.default == inspect.Parameter.empty
            default = param.default if not isempty else None

            # Create appropriate row based on type
            if annotation == str:
                row = self._create_string_row(name, default)
            elif annotation == bool:
                row = self._create_boolean_row(name, default)
            elif annotation == int:
                row = self._create_integer_row(name, default)
            else:
                continue  # Skip unsupported types

            self.add(row)
            self.widget_map[name] = row

    def _create_string_row(self, name, default):
        row = Adw.EntryRow(title=name.capitalize())
        if default is not None:
            row.set_text(str(default))
        row.connect("changed", lambda e: self.data_changed.send(e))
        return row

    def _create_boolean_row(self, name, default):
        row = Adw.ActionRow(title=name.capitalize())
        switch = Gtk.Switch()
        switch.set_active(default if default is not None else False)
        switch.set_valign(Gtk.Align.CENTER)
        row.add_suffix(switch)
        row.activatable_widget = switch
        row.switch = switch  # Store reference
        return row

    def _create_integer_row(self, name, default):
        adjustment = Gtk.Adjustment(
            value=default if default is not None else 0,
            lower=-2147483648,
            upper=2147483647,
            step_increment=1
        )
        row = Adw.SpinRow(title=name.capitalize(), adjustment=adjustment)
        row.connect("changed", lambda e: self.data_changed.send(e))
        return row

    def get_values(self):
        values = {}
        for name, row in self.widget_map.items():
            if isinstance(row, Adw.EntryRow) and hasattr(row, 'spin'):
                # Integer input
                values[name] = get_spinrow_int(row)
            elif isinstance(row, Adw.ActionRow):
                # Boolean switch
                values[name] = row.switch.get_active()
            else:
                # String input
                values[name] = row.get_text()
        return values

    def set_values(self, values):
        for name, value in values.items():
            row = self.widget_map.get(name)
            if row is None:
                continue
            if isinstance(row, Adw.EntryRow):
                row.set_text(str(value))
            elif isinstance(row, Adw.SpinRow):
                row.set_value(int(value))
            else:
                row.switch.set_active(bool(value))
        return values
