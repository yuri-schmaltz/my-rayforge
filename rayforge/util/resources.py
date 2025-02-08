import importlib.resources
from ..resources import icons


def get_icon_path(icon_name):
    """Retrieve the path of an icon inside the package."""
    with importlib.resources.path(icons, f"{icon_name}.svg") as path:
        return str(path)
