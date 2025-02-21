import math
import cairo
from ..config import getflag
from ..models.ops import Ops, MoveToCommand, LineToCommand, ArcToCommand
from ..models.machine import Machine
from .encoder import OpsEncoder


SHOW_TRAVEL_MOVES = getflag('SHOW_TRAVEL_MOVES')


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
        ctx.set_hairline(True)

        prev_point = 0, ymax
        for segment in ops.segments():
            for cmd in segment:
                match cmd, cmd.end:
                    case MoveToCommand(), (x, y):
                        adjusted_y = ymax - y

                        # Paint the travel move. We do not have to worry that
                        # there may be any unpainted path before it, because
                        # Ops.segments() ensures that each travel move opens
                        # a new segment.
                        if SHOW_TRAVEL_MOVES:
                            ctx.move_to(*prev_point)
                            ctx.set_source_rgb(.8, .8, .8)
                            ctx.line_to(x, adjusted_y)
                            ctx.stroke()
                        else:
                            ctx.move_to(x, adjusted_y)

                        prev_point = x, adjusted_y

                    case LineToCommand(), (x, y):
                        adjusted_y = ymax-y
                        ctx.line_to(x, adjusted_y)
                        prev_point = x, adjusted_y

                    case ArcToCommand(), (x, y):
                        # x, y: absolute values
                        # i, j: relative position of arc center from start point.
                        adjusted_y = ymax-y

                        # Start point is the x, y of the previous operation.
                        start_x, start_y = prev_point

                        # Draw the arc in the correct direction
                        i, j = cmd.center_offset
                        center_x = start_x+i
                        center_y = start_y+j
                        radius = math.dist(prev_point, (center_x, center_y))
                        angle1 = math.atan2(start_y - center_y, start_x - center_x)
                        angle2 = math.atan2(adjusted_y - center_y, x - center_x)
                        ctx.stroke()
                        ctx.set_source_rgb(0, 0, 1)
                        if cmd.clockwise:
                            ctx.arc(center_x, center_y, radius, angle1, angle2)
                        else:
                            ctx.arc_negative(
                                center_x,
                                center_y,
                                radius,
                                angle1,
                                angle2
                            )
                        ctx.stroke()
                        ctx.move_to(x, adjusted_y)
                        ctx.set_source_rgb(1, 0, 1)

                        prev_point = x, adjusted_y

                    case _:
                        pass  # ignore unsupported operations

            # Draw the segment.
            ctx.set_source_rgb(1, 0, 1)
            ctx.stroke()
