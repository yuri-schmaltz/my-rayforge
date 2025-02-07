import yaml
from typing import Dict, Any
from blinker import Signal
from .machine import Machine


class Config:
    def __init__(self):
        self.machine: Machine = None
        self.paned_position = 60  # in percent
        self.changed = Signal()

    def set_machine(self, machine: Machine):
        if self.machine == machine:
            return
        if self.machine:
            self.machine.changed.disconnect()
        self.machine = machine
        self.changed.send(self)
        self.machine.changed.connect(self.changed.send)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "machine": self.machine.id,
            "paned_position": self.paned_position
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any], get_machine_by_id) -> 'Config':
        config = cls()
        config.set_machine(get_machine_by_id(data.get("machine")))
        config.paned_position = data.get("paned_position",
                                         config.paned_position)
        return config


class ConfigManager:
    def __init__(self, filepath, machine_mgr):
        self.filepath = filepath
        self.machine_mgr = machine_mgr
        self.config: Config = None

        self.load_config()

    def save(self):
        with open(self.filepath, 'w') as f:
            yaml.safe_dump(self.config.to_dict(), f)

    def load_config(self) -> 'Config':
        if not self.filepath.exists():
            self.config = Config()   # Return a default config
            return self.config

        with open(self.filepath, 'r') as f:
            data = yaml.safe_load(f)
            if not data:
                return config
            config = Config.from_dict(data, self.machine_mgr.get_machine_by_id)
            self.config = config
            return config
