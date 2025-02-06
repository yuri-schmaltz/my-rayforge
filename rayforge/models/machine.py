import yaml
import uuid
import logging
from typing import List, Dict, Any

logger = logging.getLogger(__name__)


class LaserHead:
    def __init__(self):
        self.max_power: int = 1000  # Max power (0-1000 for GRBL)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "max_power": self.max_power,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'LaserHead':
        lh = cls()
        lh.max_power = data.get("max_power", lh.max_power)
        return lh


class Machine:
    name: str = 'Default Machine'
    preamble: List[str] = ["G21 ; Set units to mm",
                           "G90 ; Absolute positioning"]
    postscript: List[str] = ["G0 X0 Y0 ; Return to origin"]
    heads: List[LaserHead] = []
    max_travel_speed: int = 3000   # in mm/min
    max_cut_speed: int = 1000   # in mm/min
    dimensions: tuple[int, int] = 200, 200

    def __init__(self):
        self.id = str(uuid.uuid4())
        self.heads = [LaserHead()]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "machine": {
                "name": self.name,
                "dimensions": list(self.dimensions),
                "heads": [head.to_dict() for head in self.heads],
                "speeds": {
                    "max_cut_speed": self.max_cut_speed,
                    "max_travel_speed": self.max_travel_speed,
                },
                "gcode": {
                    "preamble": self.preamble,
                    "postscript": self.postscript,
                },
            }
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Machine':
        ma = cls()
        ma_data = data.get("machine", {})
        ma.name = ma_data.get("name", ma.name)
        ma.dimensions = tuple(ma_data.get("dimensions", ma.dimensions))
        ma.heads = [LaserHead.from_dict(o) for o in ma_data.get("heads", {})]
        speeds = ma_data.get("speeds", {})
        ma.max_cut_speed = speeds.get("max_cut_speed", ma.max_cut_speed)
        ma.max_travel_speed = speeds.get("max_travel_speed",
                                         ma.max_travel_speed)
        gcode = ma_data.get("gcode", {})
        ma.preamble = gcode.get("preamble", ma.preamble)
        ma.postscript = gcode.get("postscript", ma.postscript)
        return ma

    @classmethod
    def filename_from_id(cls, base_dir, machine_id: str) -> 'Machine':
        return base_dir / f"{machine_id}.yaml"

    def save(self, base_dir):
        machine_file = self.filename_from_id(base_dir, self.id)
        with open(machine_file, 'w') as f:
            yaml.safe_dump(self.to_dict(), f)

    @classmethod
    def load(cls, base_dir, machine_id: str) -> 'Machine':
        machine_file = cls.filename_from_id(base_dir, machine_id)
        if not machine_file.exists():
            raise FileNotFoundError(f"Machine file {machine_file} not found")
        with open(machine_file, 'r') as f:
            data = yaml.safe_load(f)
            if not data:
                err = f"WARN: skipping invalid machine file {f.name}"
                logger.error(err)
                return None
            machine = cls.from_dict(data)
            machine.id = machine_id
            return machine

    @classmethod
    def create_default(cls, base_dir):
        base_dir.mkdir(parents=True, exist_ok=True)
        machine = Machine()
        machine.save()
        return machine

    @classmethod
    def load_all(cls, base_dir):
        machines = dict()
        for file in base_dir.glob("*.yaml"):
            machine = cls.load(base_dir, file.stem)
            if machine:
                machines[machine.id] = machine
        return machines
