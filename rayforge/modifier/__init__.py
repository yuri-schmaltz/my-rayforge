# flake8: noqa:F401
import inspect
from .colorfilter import KeepColor
from .grayscale import ToGrayscale
from .modifier import Modifier
from .transparency import MakeTransparent

modifier_by_name = dict(
    [(name, obj) for name, obj in list(locals().items())
     if not name.startswith('_') or inspect.ismodule(obj)]
)
