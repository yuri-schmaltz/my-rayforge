from .processor import Processor
import cairo
import numpy as np


def convert_surface_to_greyscale(surface):
    # Determine the number of channels based on the format
    surface_format = surface.get_format()
    if surface_format != cairo.FORMAT_ARGB32:
        raise ValueError("Unsupported Cairo surface format")

    width, height = surface.get_width(), surface.get_height()
    data = surface.get_data()
    data = np.frombuffer(data, dtype=np.uint8).reshape((height, width, 4))

    # Convert RGB to grayscale using luminosity method
    gray = (0.299*data[:, :, 2]
            + 0.587*data[:, :, 1]
            + 0.114*data[:, :, 0]).astype(np.uint8)

    # Set RGB channels to gray, keep alpha unchanged
    data[:, :, :3] = gray[:, :, None]

    return surface


class ToGrayscale(Processor):
    """
    Removes colors from input surface.
    """
    @staticmethod
    def process(group):
        convert_surface_to_greyscale(group.surface)
