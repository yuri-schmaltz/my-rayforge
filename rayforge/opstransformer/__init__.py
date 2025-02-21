# flake8: noqa:F401
import inspect
from .transformer import OpsTransformer
from .arcwelder import ArcWeld
from .optimize import Optimize
from .smooth import Smooth

transformer_by_name = dict(
    [(name, obj) for name, obj in list(locals().items())
     if not name.startswith('_') or inspect.ismodule(obj)]
)
