import math
import cairo
from ..models.ops import Ops
from ..models.machine import Machine
from .encoder import OpsEncoder


class CairoEncoder(OpsEncoder):
    """
    Encodes a Ops onto a Cairo surface, respecting embedded state commands
    (color, geometry) and machine dimensions for coordinate adjustments.
    """
    def encode(self,
               ops: Ops,
               machine: Machine,
               surface: cairo.Surface,
               scale: tuple[float, float]) -> None:
        # Set up Cairo context and scaling
        ctx = cairo.Context(surface)
        ctx.set_source_rgb(1, 0, 1)

        # Calculate scaling factors from surface and machine dimensions
        # The Ops are in machine coordinates, i.e. zero point
        # at the bottom left, and units are mm.
        # Since Cairo coordinates put the zero point at the top left, we must
        # subtract Y from the machine's Y axis maximum.
        scale_x, scale_y = scale
        machine_width, machine_height = machine.dimensions
        ymax = machine_height  # For Y-axis inversion

        # Apply coordinate scaling and line width
        ctx.scale(scale_x, scale_y)
        ctx.set_line_width(1 / scale_x)  # 1-pixel line width post-scaling

        # Track rendering state
        active_path = False
        prev_point = 0, ymax

        for cmd in ops.commands:
            match cmd:
                case ('move_to', x, y):
                    if active_path:
                        ctx.set_source_rgb(1, 0, 1)
                        ctx.stroke()  # Finalize previous path

                    adjusted_y = ymax - y
                    if False:  # debug toggle for painting travel moves
                        ctx.move_to(*prev_point)
                        ctx.set_source_rgb(.8, .8, .8)
                        ctx.line_to(x, adjusted_y)
                        ctx.stroke()

                    prev_point = x, adjusted_y
                    active_path = True

                case ('line_to', x, y):
                    adjusted_y = ymax-y
                    ctx.move_to(*prev_point)
                    ctx.set_source_rgb(1, 0, 1)
                    ctx.line_to(x, adjusted_y)
                    prev_point = x, adjusted_y
                    active_path = True

                case ('arc_to', x, y, i, j, clockwise):
                    # x, y: absolute values
                    # i, j: relative position of arc center from start point.
                    adjusted_y = ymax-y
                    ctx.move_to(*prev_point)
                    ctx.set_source_rgb(1, 0, 1)

                    # Start point is the x, y of the previous operation.
                    start_x, start_y = prev_point

                    # Draw the arc in the correct direction
                    center_x = start_x+i
                    center_y = start_y+j
                    radius = math.dist(prev_point, (center_x, center_y))
                    angle1 = math.atan2(start_y - center_y, start_x - center_x)
                    angle2 = math.atan2(adjusted_y - center_y, x - center_x)
                    if clockwise:
                        ctx.arc_negative(
                            center_x,
                            center_y,
                            radius,
                            angle1,
                            angle2
                        )
                    else:
                        ctx.arc(center_x, center_y, radius, angle1, angle2)

                    prev_point = x, adjusted_y
                    active_path = True

                case _:
                    pass  # ignore unsupported operations

        # Stroke any remaining open path
        if active_path:
            ctx.stroke()
