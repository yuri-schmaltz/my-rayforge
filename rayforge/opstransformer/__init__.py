# flake8: noqa:F401
import inspect
from .transformer import OpsTransformer
from .optimize import Optimize

transformer_by_name = dict(
    [(name, obj) for name, obj in list(locals().items())
     if not name.startswith('_') or inspect.ismodule(obj)]
)
