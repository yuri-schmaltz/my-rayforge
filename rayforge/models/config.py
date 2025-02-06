import yaml
from typing import Dict, Any
from .machine import Machine


class Config:
    def __init__(self):
        self.machine: Machine = None
        self.paned_position = 60  # in percent

    def to_dict(self) -> Dict[str, Any]:
        return {
            "machine": self.machine.id,
            "paned_position": self.paned_position
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any], machines) -> 'Config':
        config = cls()
        if not data:
            return config
        config.machine = machines.get(data.get("machine"))
        config.paned_position = data.get("paned_position",
                                         config.paned_position)
        return config

    def save(self, filename):
        with open(filename, 'w') as f:
            yaml.safe_dump(self.to_dict(), f)

    @classmethod
    def load(cls, filename, machines) -> 'Config':
        if not filename.exists():
            return cls()
        with open(filename, 'r') as f:
            data = yaml.safe_load(f)
            return cls.from_dict(data, machines)
