from pathlib import Path
from platformdirs import user_config_dir
from .models.machine import Machine
from .models.config import Config

CONFIG_DIR = Path(user_config_dir("rayforge"))
MACHINE_DIR = CONFIG_DIR / "machines"
MACHINE_DIR.mkdir(parents=True, exist_ok=True)
CONFIG_FILE = CONFIG_DIR / "config.yaml"

print(f"Config dir is {CONFIG_DIR}")
machines = Machine.load_all(MACHINE_DIR)
print(f"Loaded {len(machines)} machines from config")
if not machines:
    machine = Machine.create_default(MACHINE_DIR)
    print(f"Created a default machine config {machine.id}")
    machines = Machine.load_all(MACHINE_DIR)
    print(f"Loaded {len(machines)} machines from config")

config = Config.load(CONFIG_FILE, machines)
if not config.machine:
    config.machine = list(machines.values())[0]
print(f"Config loaded. Using machine {config.machine.id}")
