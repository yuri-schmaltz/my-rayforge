import cairo
import numpy as np
import cv2
from .processor import Processor


class OutlineTracer(Processor):
    """
    Find outlines for laser cutting.
    """
    @staticmethod
    def process(group):
        # Get the surface format
        surface_format = group.surface.get_format()

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
        width, height = group.surface.get_width(), group.surface.get_height()
        buf = group.surface.get_data()
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

        # The resulting path needs to be in machine coordinates, i.e. zero
        # point must be at the bottom left, and units need to be mm.
        # Since Cairo coordinates put the zero point at the top left, we must
        # subtract Y from the machine's Y axis maximum.
        canvas = group.get_canvas()
        ymax = canvas.root.height_mm
        scale = group.get_pixels_per_mm()
        for contour in contours:
            # Smooth contour
            peri = cv2.arcLength(contour, True)
            contour = cv2.approxPolyDP(contour, 0.0001*peri, True)

            # Append (scaled to mm)
            if len(contour) > 0:
                group.pathdom.move_to(contour[0][0][0]/scale,
                                      ymax-contour[0][0][1]/scale)
                for point in contour:
                    x, y = point[0]
                    group.pathdom.line_to(x/scale, ymax-y/scale)
                group.pathdom.close_path()
