import math
from ...models.ops import Ops, \
                          LineToCommand, \
                          ArcToCommand, \
                          MoveToCommand
from ..transformer import OpsTransformer
from .points import remove_duplicates, \
                    are_colinear, \
                    arc_direction, \
                    fit_circle


def contains_command(segment, cmdcls):
    for cmd in segment:
        if isinstance(cmd, cmdcls):
            return True
    return False


def split_into_segments(commands):
    """
    Splits commands into logical segments while tracking current position.
    - Segments with arc_to are preceded by explicit or implicit move_to.
    - State commands are standalone segments.
    """
    segments = []
    current_segment = []
    current_pos = None  # Track current position

    for cmd in commands:
        if cmd.is_travel_command():
            # Start new segment
            if current_segment:
                segments.append(current_segment)
            current_segment = [cmd]
            current_pos = cmd.args

        elif isinstance(cmd, ArcToCommand):
            # Start new segment
            if contains_command(current_segment, LineToCommand):
                segments.append(current_segment)
                current_segment = [cmd]
            else:
                current_segment.append(cmd)
            current_pos = cmd.args[:2]

        elif isinstance(cmd, LineToCommand):
            # Add to current segment and track position
            if contains_command(current_segment, ArcToCommand):
                segments.append(current_segment)
                current_segment = []
            if not current_segment:
                if current_pos is None:
                    raise ValueError("line_to requires a starting position")
                current_segment.append(MoveToCommand(current_pos))
            current_segment.append(cmd)
            current_pos = cmd.args

        elif cmd.is_state_command():
            # All other commands are standalone
            if current_segment:
                segments.append(current_segment)
                current_segment = []
            segments.append([cmd])

        else:
            raise ValueError(f"Unsupported command: {cmd}")

    if current_segment:
        segments.append(current_segment)

    return segments


class ArcWeld(OpsTransformer):
    """
    Converts line sequences into arcs using pre-validated geometric utilities.
    """
    def __init__(self, tolerance=0.1, min_points=10):
        self.tolerance = tolerance  # Max allowed deviation from arc
        self.min_points = min_points  # Minimum points to attempt arc fitting

    def run(self, ops: Ops):
        segments = split_into_segments(ops.commands)
        ops.clear()

        for segment in segments:
            if contains_command(segment, LineToCommand):
                self.process_segment([cmd.args for cmd in segment], ops)
            else:
                for command in segment:
                    ops.add(command)

    def process_segment(self, segment, ops):
        if not segment:
            return

        # Process all points without adding an extra move_to
        segment = remove_duplicates(segment)
        index = 0
        n = len(segment)

        ops.move_to(*segment[0])
        while index < n:
            if index != 0:
                ops.line_to(*segment[index])
            best_arc, best_end = self._find_longest_valid_arc(segment, index)
            if best_arc:
                self._add_arc_command(segment, index, best_end, best_arc, ops)
                index = best_end
            else:
                index += 1

    def _add_arc_command(self, segment, start, end, arc, ops):
        center, radius, _ = arc
        start_point = segment[start]
        end_point = segment[end - 1]  # Use end-1 to get the correct endpoint

        # Calculate I and J offsets
        i = center[0] - start_point[0]
        j = start_point[1] - center[1]  # Inverted Y-axis

        clockwise = arc_direction(segment[start:end], center)

        ops.arc_to(end_point[0], end_point[1], i, j, clockwise)

    def _find_longest_valid_arc(self, segment, start_index):
        max_search = len(segment)-start_index

        for length in range(max_search, self.min_points-1, -1):
            end = start_index+length
            assert end - start_index >= self.min_points
            subsegment = segment[start_index:end]
            arc = fit_circle(subsegment)
            if self._is_valid_arc(subsegment, arc):
                return arc, end

        return None, start_index

    def _is_valid_arc(self, subsegment, arc):
        if arc is None:
            return False
        center, radius, error = arc
        if (error > self.tolerance
         or radius < 1
         or radius > 100
         or are_colinear(subsegment)):
            return False

        # Angular continuity checks
        max_step = math.radians(85)  # degrees between consecutive points
        angles = []
        for x, y in subsegment:
            dx = x - center[0]
            dy = y - center[1]
            angle = math.atan2(dy, dx)
            angles.append(angle)

        # Check consecutive angular steps
        for i in range(1, len(angles)):
            delta = abs(angles[i] - angles[i-1])
            delta = min(delta, 2 * math.pi - delta)  # Account for wrapping
            if delta > max_step:
                return False

        return True
