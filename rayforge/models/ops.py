import numpy as np
import math
from copy import copy
from typing import NamedTuple
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


class Command(NamedTuple):
    """
    Note that the state attribute is not set by default. It is later
    filled during the pre-processing stage, where state commands are
    removed.
    """
    name: str
    args: tuple = ()
    state: State = None  # Intended state during the executing of this command


class Ops:
    """
    Represents a set of generated path segments and instructions that
    are used for making gcode, but also to generate vector graphics
    for display.
    """
    def __init__(self):
        self.commands = []
        self.last_move_to = 0.0, 0.0

    def __iter__(self):
        return iter(self.commands)

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
        cmd = Command(name='move_to', args=self.last_move_to)
        self.commands.append(cmd)

    def line_to(self, x, y):
        cmd = Command(name='line_to', args=(float(x), float(y)))
        self.commands.append(cmd)

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
        self.commands.append(Command(
            name='arc_to',
            args=(float(x), float(y), float(i), float(j), bool(clockwise))
        ))

    def set_power(self, power: float):
        """Laser power (0-1000 for GRBL)"""
        cmd = Command(name='set_power', args=(float(power),))
        self.commands.append(cmd)

    def set_cut_speed(self, speed: float):
        """Cutting speed (mm/min)"""
        cmd = Command(name='set_cut_speed', args=(float(speed),))
        self.commands.append(cmd)

    def set_travel_speed(self, speed: float):
        """Rapid movement speed (mm/min)"""
        cmd = Command(name='set_travel_speed', args=(float(speed),))
        self.commands.append(cmd)

    def enable_air_assist(self, enable=True):
        if enable:
            self.commands.append(Command(name='enable_air_assist'))
        else:
            self.disable_air_assist()

    def disable_air_assist(self):
        self.commands.append(Command(name='disable_air_assist'))

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
        for cmd in self.commands:
            if cmd.name == 'move_to':
                last = cmd.args
            elif cmd.name == 'line_to':
                if last is not None:
                    total += math.dist(cmd.args, last)
                last = cmd.args
        return total

    def dump(self):
        print(self.commands)


if __name__ == '__main__':
    test_segment = [
        Command('move_to', (1, 1), State(power=1)),
        Command('line_to', (2, 2), State(power=2)),
        Command('arc_to',  (3, 3, 0.4, 0.4, True), State(power=3)),
        Command('line_to', (4, 4), State(power=4)),
    ]
    print(test_segment)
    print(flip_segment(test_segment))
