import gi
from .draglist import DragListBox
from .workstepbox import WorkStepBox
from .models.workplan import WorkPlan

gi.require_version("Gtk", "4.0")
from gi.repository import Gtk  # noqa: E402


class WorkPlanView(DragListBox):
    def __init__(self, workplan: WorkPlan):
        super().__init__()
        self.workplan = workplan
        self.workplan.changed.connect(self.on_workplan_changed)
        self.update()

    def update(self):
        self.remove_all()
        for step in self.workplan:
            row = Gtk.ListBoxRow()
            self.add_row(row)
            workstepbox = WorkStepBox(step)
            row.set_child(workstepbox)

    def on_workplan_changed(self, sender, **kwargs):
        self.update()
