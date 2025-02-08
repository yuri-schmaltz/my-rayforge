from typing import List
from .workpiece import WorkPiece
from .workplan import WorkPlan


class Doc:
    """
    Represents a loaded Rayforge document.
    """
    workpieces: List[WorkPiece]
    workplan: WorkPlan

    def __init__(self):
        self.workpieces = []
        self.workplan = WorkPlan("Default plan")

    def __iter__(self):
        return iter(self.workpieces)

    def add_workpiece(self, workpiece):
        self.workpieces.append(workpiece)

    def remove_workpiece(self, workpiece):
        self.workpieces.remove(workpiece)

    def has_workpiece(self):
        return bool(self.workpieces)
