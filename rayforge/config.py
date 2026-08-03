import logging
import os
from pathlib import Path

from platformdirs import user_config_dir, user_log_dir

logger = logging.getLogger(__name__)


def _get_config_dir() -> Path:
    """Get the config directory, respecting RAYFORGE_CONFIG_DIR env var."""
    env_config = os.environ.get("RAYFORGE_CONFIG_DIR")
    if env_config:
        return Path(env_config)
    return Path(user_config_dir("rayforge"))


CONFIG_DIR = _get_config_dir()
logger.info(f"Config dir is {CONFIG_DIR}")

MACHINE_DIR = CONFIG_DIR / "machines"
logger.debug(f"MACHINE_DIR is {MACHINE_DIR}")
MACHINE_DIR.mkdir(parents=True, exist_ok=True)

DIALECT_DIR = CONFIG_DIR / "dialects"
logger.debug(f"DIALECT_DIR is {DIALECT_DIR}")
DIALECT_DIR.mkdir(parents=True, exist_ok=True)

CONFIG_FILE = CONFIG_DIR / "config.yaml"
ADDONS_DIR = CONFIG_DIR / "addons"
ADDON_DATA_DIR = CONFIG_DIR / "addon_data"


def get_addon_data_dir(addon_name: str) -> Path:
    """
    Get the data directory for an addon.

    Args:
        addon_name: The canonical name of the addon.

    Returns:
        Path to the addon's data directory.
    """
    path = ADDON_DATA_DIR / addon_name
    path.mkdir(parents=True, exist_ok=True)
    return path


BUILTIN_ADDONS_DIR = Path(__file__).parent / "builtin_addons"
PRIVATE_ADDONS_DIR = Path(__file__).parent / "private_addons"

USER_DEVICES_DIR = CONFIG_DIR / "devices"
BUILTIN_DEVICES_DIR = Path(__file__).parent / "resources" / "devices"

# State files (like logs)
LOG_DIR = Path(user_log_dir("rayforge"))
logger.info(f"Log dir is {LOG_DIR}")
LOG_DIR.mkdir(parents=True, exist_ok=True)

# Material directories
USER_MATERIALS_DIR = CONFIG_DIR / "materials"
USER_RECIPES_DIR = CONFIG_DIR / "recipes"

ADDON_REGISTRY_URL = (
    "https://raw.githubusercontent.com/yuri-schmaltz/pires-forge-addons/"
    "main/registry.yaml"
)

# Analytics are disabled in Pires Forge. The upstream Umami endpoint
# is not used; users who want telemetry can opt in via their own
# reverse-proxy or by setting UMAMI_URL/UMAMI_WEBSITE_ID at build
# time.
UMAMI_URL = ""
UMAMI_WEBSITE_ID = ""


def getflag(name, default=False):
    default = "true" if default else "false"
    return os.environ.get(name, default).lower() in ("true", "1")
