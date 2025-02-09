import yaml
import uuid
import logging
from typing import List, Dict, Any
from blinker import Signal


logger = logging.getLogger(__name__)


class Laser:
    def __init__(self):
        self.max_power: int = 1000  # Max power (0-1000 for GRBL)
        self.point_size_mm: int = 0.1  # Point size in millimeters

    def to_dict(self) -> Dict[str, Any]:
        return {
            "max_power": self.max_power,
            "point_size_mm": self.point_size_mm,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Laser':
        lh = cls()
        lh.max_power = data.get("max_power", lh.max_power)
        lh.point_size_mm = data.get("point_size_mm", lh.point_size_mm)
        return lh


class Machine:
    name: str = 'Default Machine'
    preamble: List[str] = ["G21 ; Set units to mm",
                           "G90 ; Absolute positioning"]
    postscript: List[str] = ["G0 X0 Y0 ; Return to origin"]
    air_assist_on = "M8 ; Enable air assist"
    air_assist_off = "M9 ; Disable air assist"
    heads: List[Laser] = []
    max_travel_speed: int = 3000   # in mm/min
    max_cut_speed: int = 1000   # in mm/min
    dimensions: tuple[int, int] = 200, 200

    def __init__(self):
        self.id = str(uuid.uuid4())
        self.heads = [Laser()]
        self.changed = Signal()

    def set_preamble(self, preamble: List[str]):
        self.preamble = preamble
        self.changed.send(self)

    def set_postscript(self, postscript: List[str]):
        self.postscript = postscript
        self.changed.send(self)

    def set_air_assist_on(self, gcode: str|None):
        self.air_assist_on = gcode
        self.changed.send(self)

    def set_air_assist_off(self, gcode: str|None):
        self.air_assist_off = gcode
        self.changed.send(self)

    def set_max_travel_speed(self, speed: int):
        self.max_travel_speed = speed
        self.changed.send(self)

    def set_max_cut_speed(self, speed: int):
        self.max_cut_speed = speed
        self.changed.send(self)

    def set_dimensions(self, width: int, height: int):
        self.dimensions = (width, height)
        self.changed.send(self)

    def add_head(self, head: Laser):
        self.heads.append(head)
        self.changed.send(self)

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
                    "air_assist_on": self.air_assist_on,
                    "air_assist_off": self.air_assist_off,
                },
            }
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Machine':
        ma = cls()
        ma_data = data.get("machine", {})
        ma.name = ma_data.get("name", ma.name)
        ma.dimensions = tuple(ma_data.get("dimensions", ma.dimensions))
        ma.heads = [Laser.from_dict(o) for o in ma_data.get("heads", {})]
        speeds = ma_data.get("speeds", {})
        ma.max_cut_speed = speeds.get("max_cut_speed", ma.max_cut_speed)
        ma.max_travel_speed = speeds.get("max_travel_speed",
                                         ma.max_travel_speed)
        gcode = ma_data.get("gcode", {})
        ma.preamble = gcode.get("preamble", ma.preamble)
        ma.postscript = gcode.get("postscript", ma.postscript)
        ma.air_assist_on = gcode.get("air_assist_on", ma.air_assist_on)
        ma.air_assist_off = gcode.get("air_assist_off", ma.air_assist_off)
        return ma


class MachineManager:
    def __init__(self, base_dir):
        base_dir.mkdir(parents=True, exist_ok=True)
        self.base_dir = base_dir
        self.machines = dict()
        self.load()

    def filename_from_id(self, machine_id: str) -> 'Machine':
        return self.base_dir / f"{machine_id}.yaml"

    def add_machine(self, machine):
        if machine.id in self.machines:
            return
        self.machines[machine.id] = machine
        machine.changed.connect(self.on_machine_changed)

    def get_machine_by_id(self, machine_id):
        return self.machines.get(machine_id)

    def create_default_machine(self):
        machine = Machine()
        self.add_machine(machine)
        self.save_machine(machine)
        return machine

    def save_machine(self, machine):
        machine_file = self.filename_from_id(machine.id)
        with open(machine_file, 'w') as f:
            yaml.safe_dump(machine.to_dict(), f)

    def load_machine(self, machine_id: str) -> 'Machine':
        machine_file = self.filename_from_id(machine_id)
        if not machine_file.exists():
            raise FileNotFoundError(f"Machine file {machine_file} not found")
        with open(machine_file, 'r') as f:
            data = yaml.safe_load(f)
            if not data:
                msg = f"skipping invalid machine file {f.name}"
                logger.warning(msg)
                return None
        machine = Machine.from_dict(data)
        machine.id = machine_id
        self.add_machine(machine)
        return machine

    def on_machine_changed(self, machine, **kwargs):
        self.save_machine(machine)

    def load(self):
        machines = dict()
        for file in self.base_dir.glob("*.yaml"):
            machine = self.load_machine(file.stem)
            if machine:
                self.add_machine(machine)
        return machines
