import cairo
from ..models.path import Path
from ..models.machine import Machine
from .encoder import PathEncoder

class CairoEncoder(PathEncoder):
    """
    Encodes a Path onto a Cairo surface, respecting embedded state commands
    (color, geometry) and machine dimensions for coordinate adjustments.
    """
    def encode(self,
               path: Path,
               machine: Machine,
               surface: cairo.Surface,
               scale: tuple[float, float]) -> None:
        # Set up Cairo context and scaling
        ctx = cairo.Context(surface)
        ctx.set_source_rgb(1, 0, 1)  # Default magenta
        
        # Calculate scaling factors from surface and machine dimensions
        # The path is in machine coordinates, i.e. zero point
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

        for cmd in path.commands:
            match cmd:
                case ('move_to', x, y):
                    if active_path:
                        ctx.stroke()  # Finalize previous path
                    adjusted_y = ymax - y
                    ctx.move_to(x, adjusted_y)
                    active_path = True

                case ('line_to', x, y):
                    if not active_path:
                        ctx.move_to(x, ymax - y)
                        active_path = True
                    else:
                        adjusted_y = ymax - y
                        ctx.line_to(x, adjusted_y)

                case ('close_path',):
                    if active_path:
                        ctx.close_path()
                        ctx.stroke()
                        active_path = False

                case ('set_color', (r, g, b)):
                    ctx.set_source_rgb(r, g, b)

                case _:
                    pass # ignore unsupported operations

        # Stroke any remaining open path
        if active_path:
            ctx.stroke()
