import io
import cairo
import numpy as np
import cv2
from svgpathtools import svg2paths2
from ..render import SVGRenderer
from .modifier import Modifier


def prepare_surface_for_tracing(surface):
    # Get the surface format
    surface_format = surface.get_format()

    # Determine the number of channels based on the format
    if surface_format == cairo.FORMAT_ARGB32:
        channels = 4  # ARGB or RGBA
        target_fmt = cv2.COLOR_BGRA2GRAY
    elif surface_format == cairo.FORMAT_RGB24:
        channels = 3  # RGB
        target_fmt = cv2.COLOR_BGR2GRAY
    else:
        raise ValueError("Unsupported Cairo surface format")

    # Make a copy of the image.
    width, height = surface.get_width(), surface.get_height()
    buf = surface.get_data()
    img = np.frombuffer(buf, dtype=np.uint8)
    img = img.reshape(height, width, channels).copy()

    # Replace transparent pixels with white
    if channels == 4:
        alpha = img[:, :, 3]  # Extract the alpha channel
        img[alpha == 0] = 255, 255, 255, 255

    # Convert to binary image (thresholding)
    gray = cv2.cvtColor(img, target_fmt)
    _, binary = cv2.threshold(gray, 128, 255, cv2.THRESH_BINARY_INV)
    return binary


def contours2path(contours, path, pixels_per_mm, ymax):
    """
    The resulting path needs to be in machine coordinates, i.e. zero
    point must be at the bottom left, and units need to be mm.
    Since Cairo coordinates put the zero point at the top left, we must
    subtract Y from the machine's Y axis maximum.
    """
    scale_x, scale_y = pixels_per_mm
    for contour in contours:
        # Smooth contour
        peri = cv2.arcLength(contour, True)
        contour = cv2.approxPolyDP(contour, 0.0001*peri, True)

        # Append (scaled to mm)
        if len(contour) > 0:
            path.move_to(contour[0][0][0]/scale_x,
                         ymax-contour[0][0][1]/scale_y)
            for point in contour:
                x, y = point[0]
                path.line_to(x/scale_x, ymax-y/scale_y)
            path.close_path()


class OutlineTracer(Modifier):
    """
    Find external outlines for laser cutting.
    """
    def run(self, workstep, surface, pixels_per_mm, ymax):
        # Find contours of the black areas
        binary = prepare_surface_for_tracing(surface)
        contours, _ = cv2.findContours(binary,
                                       cv2.RETR_EXTERNAL,
                                       cv2.CHAIN_APPROX_SIMPLE)
        contours2path(contours, workstep.path, pixels_per_mm, ymax)


class EdgeTracer(Modifier):
    """
    Find all edges (including holes) for laser cutting.
    """
    def run(self, workstep, surface, pixels_per_mm, ymax):
        binary = prepare_surface_for_tracing(surface)

        # Retrieve all contours (including holes)
        contours, _ = cv2.findContours(binary,
                                       cv2.RETR_LIST,
                                       cv2.CHAIN_APPROX_SIMPLE)
        contours2path(contours, workstep.path, pixels_per_mm, ymax)


class SVGOutline(Modifier):
    """
    DYSFUNCT FOR NOW! THIS IS A TODO
    Transforms SVG paths to our internal Path objects, as
    outlines for laser cutting.
    """
    def run(self, workstep, surface, pixels_per_mm, ymax):
        # Use svgpathtools to extract paths and attributes of each of the
        # SVG workpieces.
        for workpiece in workstep.workpieces:
            if not issubclass(workpiece.renderer, SVGRenderer):
                continue  # not an SVG

            fp = io.Bytes(workpiece.data)
            paths, attributes, svg_attributes = svg2paths2(fp)

            width = svg_attributes.get('width'),
            height = svg_attributes.get('height')
            for svgpath, attr in zip(paths, attributes):
                print("NOT IMPLEMENTED", svgpath, attr, width, height)
                # TODO: append stuff to workstep.path
