# flake8: noqa:F401
import inspect
from .renderer import Renderer
from .dxf import DXFRenderer
from .pdf import PDFRenderer
from .png import PNGRenderer
from .svg import SVGRenderer

def isrenderer(obj):
    return (inspect.isclass(obj)
            and issubclass(obj, Renderer)
            and not obj is Renderer)

renderers = [obj for name, obj in list(locals().items()) if isrenderer(obj)]

renderer_by_mime_type = dict()
for renderer in renderers:
    for mime_type in renderer.mime_types:
        renderer_by_mime_type[mime_type] = renderer
