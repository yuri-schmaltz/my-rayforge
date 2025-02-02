import cairo
import numpy as np
import cv2
from .processor import Processor


class OutlineTracer(Processor):
    """
    Find outlines for laser cutting.
    """
    @staticmethod
    def process(item):
        # Get the surface format
        surface_format = item.surface.get_format()

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
        width, height = item.surface.get_width(), item.surface.get_height()
        buf = item.surface.get_data()
        img = np.frombuffer(buf, dtype=np.uint8)
        img = img.reshape(height, width, channels).copy()

        # Replace transparent pixels with white
        if channels == 4:
            alpha = img[:, :, 3]  # Extract the alpha channel
            img[alpha == 0] = 255, 255, 255, 255

        # Convert to binary image (thresholding)
        gray = cv2.cvtColor(img, target_fmt)
        _, binary = cv2.threshold(gray, 128, 255, cv2.THRESH_BINARY_INV)

        # Find contours of the black areas
        contours, _ = cv2.findContours(binary,
                                       cv2.RETR_EXTERNAL,
                                       cv2.CHAIN_APPROX_SIMPLE)

        for contour in contours:
            if len(contour) > 0:
                item.pathdom.move_to(contour[0][0][0], contour[0][0][1])
                for point in contour:
                    x, y = point[0]
                    item.pathdom.line_to(x, y)
                item.pathdom.close_path()
