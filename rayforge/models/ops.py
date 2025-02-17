import numpy as np
import math
from copy import copy
from dataclasses import dataclass


@dataclass
class State:
    power: int = 0
    air_assist: bool = False
    cut_speed: int = None
    travel_speed: int = None

    def allow_rapid_change(self, target_state):
        """
        Returns True if a change to the target state should be allowed
        in a rapid manner, i.e. for each gcode instruction. For example,
        changing air-assist should not be done too frequently, because
        it could damage the air pump.

        Changing the laser power rapidly is unproblematic.
        """
        return self.air_assist == target_state.air_assist


@dataclass
class Op:
    command: str
    args: object
    state: State


def preprocess_commands(commands):
    """
    Preprocess the commands, enriching each command by the indended
    state of the machine. This is to prepare for re-ordering without
    changing the intended state during each command.

    Returns a list of Op objects. Any state commands are wipe out,
    as the state is now included in every operation.
    """
    operations = []
    state = State()
    for command in commands:
        match command:
            case ('set_power', power):
                state.power = power
            case ('set_cut_speed', speed):
                state.cut_speed = speed
            case ('set_travel_speed', speed):
                state.travel_speed = speed
            case ('enable_air_assist',):
                state.air_assist = True
            case ('disable_air_assist',):
                state.air_assist = False
            case _:
                cmd, *args = command
                operations.append(Op(cmd, args, copy(state)))
    return operations


def split_long_segments(operations):
    """
    Split a list of operations such that segments where air assist
    is enabled are separated from segments where it is not. We
    need this because these segments must remain in order,
    so we need to separate them and run the path optimizer on
    each segment individually.

    The result is a list of Op lists.
    """
    if len(operations) <= 1:
        return [operations]

    segments = [[operations[0]]]
    last_state = operations[0].state
    for op in operations:
        if last_state.allow_rapid_change(op.state):
            segments[-1].append(op)
        else:
            # If rapid state change is not allowed, add
            # it to a new long segment.
            segments.append([op])
    return segments


def split_segments(operations):
    """
    Split a list of commands into segments. We use it to prepare
    for reordering the segments for travel distance minimization.

    Returns a list of segments. In other words, a list of list[Op].
    """
    segments = []
    current_segment = []
    for op in operations:
        if op.command == 'move_to':
            if current_segment:
                segments.append(current_segment)
            current_segment = [op]
        elif op.command in ('line_to', 'arc_to'):
            current_segment.append(op)
        else:
            raise ValueError('unexpected operation '+op.command)

    if current_segment:
        segments.append(current_segment)
    return segments


def flip_segment(segment):
    """
    The states attached to each point descibe the intended
    machine state while traveling TO the point.

    Example:
      state:     A            B            C           D
      points:   -> move_to 1 -> line_to 2 -> arc_to 3 -> line_to 4

    After flipping this sequence, the state is in the wrong position:

      state:     D            C           B            A
      points:   -> line_to 4 -> arc_to 3 -> line_to 2 -> move_to 1

    Note that for example the edge between point 3 and 2 no longer has
    state C, it is B instead. 4 -> 3 should be D, but is C.
    So we have to shift the state and the command to the next point.
    Correct:

      state:     A            D            C           B
      points:   -> move_to 4 -> line_to 3 -> arc_to 2 -> line_to 1
    """
    length = len(segment)
    if length <= 1:
        return segment

    new_segment = []
    for i in range(length-1, -1, -1):
        prev_op = segment[(i+1) % length]
        new_op = copy(segment[i])
        new_op.state = prev_op.state
        new_op.command = prev_op.command
        new_op.args = new_op.args[:2]

        # Fix arc_to parameters
        if new_op.command == 'arc_to' and i > 0:
            # Get original arc (prev op in original segment)
            orig_op = segment[i+1]
            x_end, y_end, i_orig, j_orig, clockwise_orig = orig_op.args

            # Calculate center and new offsets
            x_start, y_start = new_op.args[:2]
            center_x = x_start + i_orig
            center_y = y_start + j_orig
            new_i = center_x - x_end
            new_j = center_y - y_end
            new_clockwise = not clockwise_orig

            # Update arc parameters
            new_op.args = x_end, y_end, new_i, new_j, new_clockwise

        new_segment.append(new_op)

    return new_segment


def greedy_order_segments(segments):
    """
    Greedy ordering using vectorized math.dist computations.
    Part of the path optimization algorithm.

    It is assumed that the input segments contain only Op objects
    that are NOT state commands (such as 'set_power'), so it is
    ensured that each Op performs a position change (i.e. it has
    x,y coordinates).
    """
    if not segments:
        return []

    ordered = []
    current_seg = segments[0]
    ordered.append(current_seg)
    current_pos = np.array(current_seg[-1].args)
    remaining = segments[1:]
    while remaining:
        # Note that "op.args" contains x,y coordinates, because the
        # segments do not contain any state commands.
        # Find the index of the best next path to take, i.e. the
        # Op that adds the smalles amount of travel distance.
        starts = np.array([seg[0].args for seg in remaining])
        ends = np.array([seg[-1].args for seg in remaining])
        d_starts = np.linalg.norm(starts - current_pos, axis=1)
        d_ends = np.linalg.norm(ends - current_pos, axis=1)
        candidate_dists = np.minimum(d_starts, d_ends)
        best_idx = int(np.argmin(candidate_dists))
        best_seg = remaining.pop(best_idx)

        # Flip candidate if its end is closer.
        if d_ends[best_idx] < d_starts[best_idx]:
            best_seg = flip_segment(best_seg)

        start_op = best_seg[0]
        start_op_command = start_op.command
        if start_op_command != 'move_to':
            end_op = best_seg[-1]
            start_op_state = start_op.state
            end_op_command = end_op.command
            end_op_state = end_op.state

            start_op.command = end_op_command
            start_op.state = end_op_state
            end_op.command = start_op_command
            end_op.state = start_op_state

        ordered.append(best_seg)
        current_pos = np.array(best_seg[-1].args)

    return ordered


def flip_segments(ordered):
    """
    Flip each segment if doing so lowers the sum of the incoming
    and outgoing travel.
    """
    improved = True
    while improved:
        improved = False
        for i in range(1, len(ordered)):
            # Calculate cost of travel (=travel distance from last segment
            # +travel distance to next segment)
            prev_segment_end = ordered[i-1][-1].args
            segment = ordered[i]
            cost = math.dist(prev_segment_end, segment[0].args)
            if i < len(ordered)-1:
                cost += math.dist(segment[-1].args, ordered[i+1][0].args)

            # Flip and calculate the flipped cost.
            flipped = flip_segment(segment)
            flipped_cost = math.dist(prev_segment_end, flipped[0].args)
            if i < len(ordered)-1:
                flipped_cost += math.dist(flipped[-1].args,
                                          ordered[i+1][0].args)

            # Choose the shorter one.
            if flipped_cost < cost:
                ordered[i] = flipped
                improved = True

    return ordered


def two_opt(ordered, max_iter=1000):
    """
    2-opt: try reversing entire sub-sequences if that lowers the travel cost.
    """
    n = len(ordered)
    if n < 3:
        return ordered
    iter_count = 0
    improved = True
    while improved and iter_count < max_iter:
        improved = False
        for i in range(n-2):
            for j in range(i+2, n):
                A_end = ordered[i][-1]
                B_start = ordered[i+1][0]
                E_end = ordered[j][-1]
                if j < n - 1:
                    F_start = ordered[j+1][0]
                    curr_cost = math.dist(A_end.args, B_start.args) \
                              + math.dist(E_end.args, F_start.args)
                    new_cost = math.dist(A_end.args, E_end.args) \
                             + math.dist(B_start.args, F_start.args)
                else:
                    curr_cost = math.dist(A_end.args, B_start.args)
                    new_cost = math.dist(A_end.args, E_end.args)
                if new_cost < curr_cost:
                    sub = ordered[i+1:j+1]
                    # Reverse order and flip each segment.
                    for n in range(len(sub)):
                        sub[n] = flip_segment(sub[n])
                    ordered[i+1:j+1] = sub[::-1]
                    improved = True
        iter_count += 1
    return ordered


class Ops:
    """
    Represents a set of generated path segments and instructions that
    are used for making gcode, but also to generate vector graphics
    for display.
    """
    def __init__(self):
        self.commands = []
        self.last_move_to = 0.0, 0.0

    def __add__(self, ops):
        result = Ops()
        result.commands = self.commands + ops.commands
        return result

    def __mul__(self, count):
        result = Ops()
        result.commands = count*self.commands
        return result

    def __len__(self):
        return len(self.commands)

    def clear(self):
        self.commands = []

    def move_to(self, x, y):
        self.last_move_to = float(x), float(y)
        self.commands.append(('move_to', *self.last_move_to))

    def line_to(self, x, y):
        self.commands.append(('line_to', float(x), float(y)))

    def close_path(self):
        """
        Convenience method that wraps line_to(). Makes a line to
        the last move_to point.
        """
        self.line_to(*self.last_move_to)

    def arc_to(self, x, y, i, j, clockwise=True):
        """
        Adds an arc command with specified endpoint, center offsets,
        and direction (cw/ccw).
        """
        self.commands.append((
            'arc_to',
            float(x), float(y), float(i), float(j),
            bool(clockwise)
        ))

    def set_power(self, power: float):
        """Laser power (0-1000 for GRBL)"""
        self.commands.append(('set_power', float(power)))

    def set_cut_speed(self, speed: float):
        """Cutting speed (mm/min)"""
        self.commands.append(('set_cut_speed', float(speed)))

    def set_travel_speed(self, speed: float):
        """Rapid movement speed (mm/min)"""
        self.commands.append(('set_travel_speed', float(speed)))

    def enable_air_assist(self, enable=True):
        if enable:
            self.commands.append(('enable_air_assist',))
        else:
            self.disable_air_assist()

    def disable_air_assist(self):
        self.commands.append(('disable_air_assist',))

    def optimize(self, max_iter=1000):
        """
        Uses the 2-opt swap algorithm to address the Traveline Salesman Problem
        to minimize travel moves in the GCode.

        This is made harder by the fact that some commands cannot be
        reordered. For example, if the ops contains multiple commands
        to toggle air-assist, we cannot reorder the operations without
        ensuring that air-assist remains on for the sections that need it.
        Ops optimization may lead to a situation where the number of
        air assist toggles is multiplied, which could be detrimental
        to the health of the air pump.

        To avoid these problems, we implement the following process:

        1. Preprocess the Ops sequentially, duplicating the intended
           state (e.g. cutting, power, ...) and attaching it to the each
           command. Here we also drop all state commands.

        2. Split the ops into non-reorderable segments. Segment in this
           step means an "as long as possible" sequence that may still
           include sub-segments, as long as those sub-segments are
           reorderable.

        3. Split the long segments into short, re-orderable sub sequences.

        4. Re-order the sub sequences to minimize travel distance.

        5. Re-assemble the Ops object.
        """
        # 1. Preprocess such that each operation has a state.
        # This also causes all state commands to be dropped - we
        # need to re-add them later.
        operations = preprocess_commands(self.commands)

        # 2. Split the operations into long segments where
        # the state stays more or less the same, i.e. no switching
        # of states that we should be careful with, such as toggling
        # air assist.
        long_segments = split_long_segments(operations)

        # 3. Split the long segments into small, re-orderable
        # segments.
        result = []
        for long_segment in long_segments:
            # 4. Reorder to minimize the distance.
            segments = split_segments(long_segment)
            segments = greedy_order_segments(segments)
            segments = flip_segments(segments)
            result += two_opt(segments, max_iter=max_iter)

        # 5. Reassemble the ops, reintroducing state change commands.
        self.commands = []
        for segment in result:
            if not segment:
                continue  # skip empty segments

            prev_state = State()

            for op in segment:
                if op.state.air_assist != prev_state.air_assist:
                    self.enable_air_assist(op.state.air_assist)
                if op.state.power != prev_state.power:
                    self.set_power(op.state.power)
                if op.state.cut_speed != prev_state.cut_speed:
                    self.set_cut_speed(op.state.cut_speed)
                if op.state.travel_speed != prev_state.travel_speed:
                    self.set_travel_speed(op.state.travel_speed)

                if op.command == 'line_to':
                    self.line_to(*op.args)
                elif op.command == 'move_to':
                    self.move_to(*op.args)
                elif op.command == 'arc_to':
                    self.arc_to(*op.args)
                else:
                    raise ValueError('unexpected command '+op.command)

    def get_frame(self, power=None, speed=None):
        """
        Returns a new Ops object containing four move_to operations forming
        a frame around the occupied area of the original Ops. The occupied
        area includes all points from line_to and close_path commands.
        """
        occupied_points = []
        last_point = None
        for cmd in self.commands:
            if cmd[0] == 'move_to':
                _, *last_point = cmd
            elif cmd[0] == 'line_to':
                _, x, y = cmd
                occupied_points.append(last_point)
                occupied_points.append((x, y))
                last_point = x, y

        if not occupied_points:
            return Ops()

        xs = [p[0] for p in occupied_points]
        ys = [p[1] for p in occupied_points]
        min_x, max_x = min(xs), max(xs)
        min_y, max_y = min(ys), max(ys)

        frame_ops = Ops()
        if power is not None:
            frame_ops.set_power(power)
        if speed is not None:
            frame_ops.set_cut_speed(speed)
        frame_ops.move_to(min_x, min_y)
        frame_ops.line_to(min_x, max_y)
        frame_ops.line_to(max_x, max_y)
        frame_ops.line_to(max_x, min_y)
        frame_ops.line_to(min_x, min_y)
        return frame_ops

    def distance(self):
        """
        Calculates the total distance of all moves. Mostly exists to help
        debug the optimize() method.
        """
        total = 0.0

        last = None
        for op, *args in self.commands:
            if op == 'move_to':
                if last is not None:
                    total += math.dist(args, last)
                last = args
            elif op == 'line_to':
                if last is not None:
                    total += math.dist(args, last)
                last = args
        return total

    def cut_distance(self):
        """
        Like distance(), but only counts cut distance.
        """
        total = 0.0

        last = None
        for op, *args in self.commands:
            if op == 'move_to':
                last = args
            elif op == 'line_to':
                if last is not None:
                    total += math.dist(args, last)
                last = args
        return total

    def dump(self):
        print(self.commands)


if __name__ == '__main__':
    test_segment = [
        Op('move_to', (1, 1), State(power=1)),
        Op('line_to', (2, 2), State(power=2)),
        Op('arc_to',  (3, 3, 0.4, 0.4, True), State(power=3)),
        Op('line_to', (4, 4), State(power=4)),
    ]
    print(test_segment)
    print(flip_segment(test_segment))
