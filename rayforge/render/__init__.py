# flake8: noqa:F401
import inspect
from .renderer import Renderer
from .png import PNGRenderer
from .svg import SVGRenderer

renderer_by_name = dict(
    [(name, obj) for name, obj in list(locals().items())
     if not name.startswith('_') or inspect.ismodule(obj)]
)
