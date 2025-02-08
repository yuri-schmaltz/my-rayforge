from typing import List
from .workpiece import WorkPiece
from .workstep import WorkStep


class Doc:
    """
    Represents a loaded Rayforge document.
    """
    workpieces: List[WorkPiece]
    worksteps: List[WorkStep]

    def __init__(self):
        self.workpieces = []
        self.worksteps = []

    def add_workstep(self, workstep):
        self.worksteps.append(workstep)

    def remove_workstep(self, workstep):
        self.worksteps.remove(workstep)

    def add_workpiece(self, workpiece):
        self.workpieces.append(workpiece)

    def remove_workpiece(self, workpiece):
        self.workpieces.remove(workpiece)

    def has_workpiece(self):
        return bool(self.workpieces)
