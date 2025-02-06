import yaml
import uuid
from typing import List, Dict, Any
from pathlib import Path
from platformdirs import user_config_dir
from render import Renderer
from modifier import Modifier, MakeTransparent, ToGrayscale, OutlineTracer

CONFIG_DIR = Path(user_config_dir("rayforge"))
MACHINE_DIR = CONFIG_DIR / "machines"

print(f"Config dir is {CONFIG_DIR}")


class LaserHead:
    def __init__(self):
        self.min_power: int = 0
        self.max_power: int = 1000  # Max power (0-1000 for GRBL)

    def to_yaml(self) -> Dict[str, Any]:
        return {
            "min_power": self.min_power,
            "max_power": self.max_power,
        }

    @classmethod
    def from_yaml(cls, data: Dict[str, Any]) -> 'LaserHead':
        lh = cls()
        lh.min_power = data.get("min_power", lh.min_power)
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

    def to_yaml(self) -> Dict[str, Any]:
        return {
            "machine": {
                "name": self.name,
                "dimensions": list(self.dimensions),
                "heads": [head.to_yaml() for head in self.heads],
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
    def from_yaml(cls, data: Dict[str, Any]) -> 'Machine':
        ma = cls()
        ma_data = data.get("machine", {})
        ma.name = ma_data.get("name", ma.name)
        ma.dimensions = tuple(ma_data.get("dimensions", ma.dimensions))
        ma.heads = [LaserHead.from_yaml(o) for o in ma_data.get("heads", {})]
        speeds = ma_data.get("speeds", {})
        ma.max_cut_speed = speeds.get("max_cut_speed", ma.max_cut_speed)
        ma.max_travel_speed = speeds.get("max_travel_speed",
                                         ma.max_travel_speed)
        gcode = ma_data.get("gcode", {})
        ma.preamble = gcode.get("preamble", ma.preamble)
        ma.postscript = gcode.get("postscript", ma.postscript)
        return ma

    @classmethod
    def filename_from_id(cls, machine_id: str) -> 'Machine':
        return MACHINE_DIR / f"{machine_id}.yaml"

    def save(self):
        machine_file = self.filename_from_id(self.id)
        with open(machine_file, 'w') as f:
            yaml.safe_dump(self.to_yaml(), f)

    @classmethod
    def load(cls, machine_id: str) -> 'Machine':
        machine_file = cls.filename_from_id(machine_id)
        if not machine_file.exists():
            raise FileNotFoundError(f"Machine file {machine_file} not found")
        with open(machine_file, 'r') as f:
            data = yaml.safe_load(f)
            if not data:
                print(f"WARN: skipping invalid machine file {f.name}")
                return None
            machine = cls.from_yaml(data)
            machine.id = machine_id
            return machine

    @classmethod
    def create_default(cls):
        MACHINE_DIR.mkdir(parents=True, exist_ok=True)
        machine = Machine()
        machine.save()
        print(f"Created a default machine config {machine.id}")

    @classmethod
    def load_all(cls):
        machines = dict()
        for file in MACHINE_DIR.glob("*.yaml"):
            machine = cls.load(file.stem)
            if machine:
                machines[machine.id] = machine
        return machines


machines = Machine.load_all()
print(f"Loaded {len(machines)} machines from config")
if not machines:
    Machine.create_default()
    machines = Machine.load_all()
    print(f"Loaded {len(machines)} machines from config")


class Config:
    def __init__(self):
        self.machine: Machine = list(machines.values())[0]
        self.paned_position = 60  # in percent

    def to_yaml(self) -> Dict[str, Any]:
        return {
            "machine": self.machine.id,
            "paned_position": self.paned_position
        }

    @classmethod
    def from_yaml(cls, data: Dict[str, Any]) -> 'Config':
        config = cls()
        if not data:
            return config
        config.machine = machines.get(data.get("machine", config.machine.id))
        config.paned_position = data.get("paned_position",
                                         config.paned_position)
        return config

    def save(self):
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        config_file = CONFIG_DIR / "config.yaml"
        with open(config_file, 'w') as f:
            yaml.safe_dump(self.to_yaml(), f)

    @classmethod
    def load(cls) -> 'Config':
        config_file = CONFIG_DIR / "config.yaml"
        if not config_file.exists():
            return cls()
        with open(config_file, 'r') as f:
            data = yaml.safe_load(f)
            return cls.from_yaml(data)


config = Config.load()
print(f"Config loaded. Using machine {config.machine.id}")


class WorkPiece:
    """
    A WorkPiece represents a real world work piece, It is usually
    loaded from an image file and serves as input for all other
    operations.
    """
    name: str
    data: bytes
    renderer: Renderer

    def __init__(self, name):
        self.name = name

    def get_aspect_ratio(self):
        return self.renderer.get_aspect_ratio(self.data)

    @staticmethod
    def from_file(filename, renderer):
        wp = WorkPiece(filename)
        with open(filename, 'rb') as fp:
            wp.data = renderer.prepare(fp.read())
        wp.renderer = renderer
        return wp

    def dump(self, indent=0):
        print("  "*indent, self.name, self.renderer.label)


class Path:
    """
    Represents a set of generated paths that are used for
    making gcode, but also to generate vactor graphics for display.
    """
    def __init__(self):
        self.paths = []

    def clear(self):
        self.paths = []

    def move_to(self, x, y):
        self.paths.append(('move_to', x, y))

    def line_to(self, x, y):
        self.paths.append(('line_to', x, y))

    def close_path(self):
        self.paths.append(('close_path',))

    def dump(self):
        print(self.paths)


class WorkStep:
    """
    A WorkStep is a set of Modifiers that operate on a set of
    WorkPieces. It normally generates a Path in the end, but
    may also include modifiers that manipulate the input image.
    """
    name: str
    description: str = 'An operation on a group of workpieces'
    workpieces: list[WorkPiece]
    modifiers: list[Modifier]
    path: Path

    def __init__(self, name):
        self.name = name
        self.workpieces = []
        self.modifiers = [
            MakeTransparent(),
            ToGrayscale(),
            OutlineTracer(),
        ]
        self.path = Path()

    def add_workpiece(self, workpiece: WorkPiece):
        self.workpieces.append(workpiece)

    def remove_workpiece(self, workpiece):
        self.workpieces.remove(workpiece)

    def dump(self, indent=0):
        print("  "*indent, self.name)
        for workpiece in self.workpieces:
            workpiece.dump(1)


class Doc:
    """
    Represents a loaded Rayforge document.
    """
    workpieces: list[WorkPiece]
    worksteps: list[WorkStep]

    def __init__(self):
        self.workpieces = []
        self.worksteps = []

    def add_workstep(self, workstep):
        self.worksteps.append(workstep)

    def add_workpiece(self, workpiece, workstep=None):
        self.workpieces.append(workpiece)
        if workstep:
            workstep.add_workpiece(workpiece)

    def has_workpiece(self):
        return bool(self.workpieces)
