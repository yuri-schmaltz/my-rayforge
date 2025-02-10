# flake8: noqa:F401
import inspect
from .modifier import Modifier
from .transparency import MakeTransparent
from .grayscale import ToGrayscale
from .outline import OutlineTracer
from .optimize import Optimizer
from .rasterize import Rasterizer

modifier_by_name = dict(
    [(name, obj) for name, obj in list(locals().items())
     if not name.startswith('_') or inspect.ismodule(obj)]
)
