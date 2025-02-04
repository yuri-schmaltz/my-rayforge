import gi
from groupbox import GroupBox
from draglist import DragListBox
from workarea import Group, WorkAreaItem

gi.require_version("Gtk", "4.0")
from gi.repository import Gtk, Gdk  # noqa: E402


class GroupWidget(GroupBox):
    def __init__(self, group: Group):
        # Hint: possible icon names can be found using gtk3-icon-browser
        super().__init__(group.name,
                         group.description,
                         icon_name=None)

        self.listbox = DragListBox()
        self.add_child(self.listbox)

        for child in group.children:
            self.add_item(child)

    def add_item(self, item: WorkAreaItem):
        label = Gtk.Label(label=item.name)
        label.set_xalign(0)
        row = Gtk.ListBoxRow()
        row.set_child(label)
        self.listbox.add_row(row)


if __name__ == "__main__":
    class GroupWindow(Gtk.ApplicationWindow):
        def __init__(self, **kwargs):
            super().__init__(**kwargs)

            group = Group('My test group', 0, 0, 300, 300)
            group.add(WorkAreaItem('Item one', 0, 0, 10, 10,
                                   renderer=object,
                                   data=object))

            group_widget = GroupWidget(group)
            self.set_child(group_widget)
            self.set_default_size(300, 200)

    def on_activate(app):
        win = GroupWindow(application=app)
        win.present()

    app = Gtk.Application(application_id="org.example.groupviewexample")
    app.connect('activate', on_activate)
    app.run()
