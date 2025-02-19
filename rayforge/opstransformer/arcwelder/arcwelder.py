import math
import numpy as np
from ...models.ops import Ops, Command, State
from ..transformer import OpsTransformer
from .points import remove_duplicates, \
                    are_colinear, \
                    arc_direction, \
                    fit_circle

def contains_command(segment, cmdname):
    for cmd in segment:
        if cmd.name == cmdname:
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
        if cmd.name == 'move_to':
            # Start new segment
            if current_segment:
                segments.append(current_segment)
            current_segment = [cmd]
            current_pos = cmd.args

        elif cmd.name == 'arc_to':
            # Start new segment
            if contains_command(current_segment, 'line_to'):
                segments.append(current_segment)
                current_segment = [cmd]
            else:
                current_segment.append(cmd)
            current_pos = cmd.args[:2]

        elif cmd.name == 'line_to':
            # Add to current segment and track position
            if contains_command(current_segment, 'arc_to'):
                segments.append(current_segment)
                current_segment = []
            if not current_segment:
                if current_pos is None:
                    raise ValueError("line_to requires a starting position")
                current_segment.append(Command('move_to', current_pos))
            current_segment.append(cmd)
            current_pos = cmd.args

        elif cmd.name in ('set_power',
                          'set_cut_speed',
                          'set_travel_speed',
                          'enable_air_assist',
                          'disable_air_assist'):
            # All other commands are standalone
            if current_segment:
                segments.append(current_segment)
                current_segment = []
            segments.append([cmd])

        else:
            raise ValueError(f"Unsupported command: {cmd.name}")
    
    if current_segment:
        segments.append(current_segment)
    
    return segments

class ArcWeld(OpsTransformer):
    """
    Converts line sequences into arcs using pre-validated geometric utilities.
    """
    def __init__(self, tolerance=0.1, min_points=5):
        self.tolerance = tolerance  # Max allowed deviation from arc
        self.min_points = min_points  # Minimum points to attempt arc fitting

    def run(self, ops: Ops):
        segments = split_into_segments(ops.commands)
        ops.clear()
        
        for segment in segments:
            if segment[0].name in ('set_power',
                                   'set_cut_speed',
                                   'set_travel_speed',
                                   'enable_air_assist',
                                   'disable_air_assist'):
                getattr(ops, segment[0].name)(*segment[0].args)
            else:
                self.process_segment([cmd.args for cmd in segment], ops)

    def process_segment(self, segment, ops):
        if not segment:
            return
        
        # Process all points without adding an extra move_to
        segment = remove_duplicates(segment)
        index = 0
        n = len(segment)

        while index < n:
            best_arc, best_end = self._find_longest_valid_arc(segment, index)
            if best_arc and (best_end - index) >= self.min_points:
                self._add_arc_command(segment, index, best_end, best_arc, ops)
                index = best_end
            else:
                # Only add move_to if it's the first command in the segment
                if index == 0:
                    ops.move_to(*segment[index])
                else:
                    ops.line_to(*segment[index])
                index += 1

    def _add_arc_command(self, segment, start, end, arc, ops):
        center, radius, _ = arc
        start_point = segment[start]
        end_point = segment[end - 1]  # Use end-1 to get the correct endpoint

        # Add move_to if necessary
        if start == 0:
            ops.move_to(*start_point)
        else:
            ops.line_to(*start_point)

        # Calculate I and J offsets
        i = center[0] - start_point[0]
        j = start_point[1] - center[1]  # Inverted Y-axis

        clockwise = arc_direction(segment[start:end], center)

        ops.arc_to(end_point[0], end_point[1], i, j, clockwise)

    def _find_longest_valid_arc(self, segment, start_index):
        best_arc = None
        best_end = start_index
        max_search = len(segment)
        
        for end in range(max_search, start_index + self.min_points - 1, -1):
            subsegment = segment[start_index:end]
            if len(subsegment) < self.min_points:
                continue
                
            arc = fit_circle(subsegment)
            if self._is_valid_arc(subsegment, arc) and end > best_end:
                best_arc = arc
                best_end = end
        
        return best_arc, best_end

    def _is_valid_arc(self, subsegment, arc):
        if arc is None:
            return False
        center, radius, error = arc
        if not (
            error <= self.tolerance
            and 1 < radius < 100  # Practical radius constraints
            and not are_colinear(subsegment)
        ):
            return False

        # Angular continuity checks
        max_step = math.radians(89)  # 89 degrees between consecutive points
        max_total_span = math.radians(180)  # Total arc span <= 180 degrees
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
        
        # Check total angular span
        total_span = abs(angles[-1] - angles[0])
        total_span = min(total_span, 2 * math.pi - total_span)
        if total_span > max_total_span:
            return False
        
        return True
