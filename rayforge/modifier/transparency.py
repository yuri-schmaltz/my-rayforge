from .modifier import Modifier
import cairo
import numpy as np


def make_transparent(surface, threshold=250):
    if surface.get_format() != cairo.FORMAT_ARGB32:
        raise ValueError("Surface must be in ARGB32 format.")

    width, height = surface.get_width(), surface.get_height()
    stride = surface.get_stride()

    # Get pixel data as a NumPy array
    data = surface.get_data()
    buf = np.frombuffer(data, dtype=np.uint8).reshape((height, stride))

    # Convert to 32-bit ARGB view
    argb = buf.view(dtype=np.uint32)[:, :width]

    # Extract channels
    r = (argb >> 16) & 0xFF  # Red
    g = (argb >> 8) & 0xFF   # Green
    b = argb & 0xFF          # Blue

    # Find "almost white" pixels
    brightness = (r.astype(np.uint16)
                  + g.astype(np.uint16)
                  + b.astype(np.uint16)) // 3
    mask = brightness >= threshold

    # Set these pixels to transparent
    argb[mask] = (0x00 << 24) | (r[mask] << 16) | (g[mask] << 8) | b[mask]

    # No need to return anything as the surface is modified in place


class MakeTransparent(Modifier):
    """
    Makes white pixels transparent.
    """
    def run(self, workstep, surface, pixels_per_mm, ymax):
        make_transparent(surface)
