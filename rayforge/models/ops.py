import math
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
    args: tuple = ()
    state: State = None  # Intended state during the executing of this command

    def is_state_command(self):
        return False

    def is_cutting_command(self):
        """Whether it is a cutting movement"""
        return False

    def is_travel_command(self):
        """Whether it is a non-cutting movement"""
        return False


class MoveToCommand(Command):
    def is_travel_command(self):
        return True


class LineToCommand(Command):
    def is_cutting_command(self):
        return True


class ArcToCommand(Command):
    def is_cutting_command(self):
        return True


class SetPowerCommand(Command):
    def is_state_command(self):
        return True


class SetCutSpeedCommand(Command):
    def is_state_command(self):
        return True


class SetTravelSpeedCommand(Command):
    def is_state_command(self):
        return True


class EnableAirAssistCommand(Command):
    def is_state_command(self):
        return True


class DisableAirAssistCommand(Command):
    def is_state_command(self):
        return True


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

    def add(self, command):
        self.commands.append(command)

    def move_to(self, x, y):
        self.last_move_to = float(x), float(y)
        cmd = MoveToCommand(args=self.last_move_to)
        self.commands.append(cmd)

    def line_to(self, x, y):
        cmd = LineToCommand(args=(float(x), float(y)))
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
        self.commands.append(ArcToCommand(
            args=(float(x), float(y), float(i), float(j), bool(clockwise))
        ))

    def set_power(self, power: float):
        """Laser power (0-1000 for GRBL)"""
        cmd = SetPowerCommand(args=(float(power),))
        self.commands.append(cmd)

    def set_cut_speed(self, speed: float):
        """Cutting speed (mm/min)"""
        cmd = SetCutSpeedCommand(args=(float(speed),))
        self.commands.append(cmd)

    def set_travel_speed(self, speed: float):
        """Rapid movement speed (mm/min)"""
        cmd = SetTravelSpeedCommand(args=(float(speed),))
        self.commands.append(cmd)

    def enable_air_assist(self, enable=True):
        if enable:
            self.commands.append(EnableAirAssistCommand())
        else:
            self.disable_air_assist()

    def disable_air_assist(self):
        self.commands.append(DisableAirAssistCommand())

    def get_frame(self, power=None, speed=None):
        """
        Returns a new Ops object containing four move_to operations forming
        a frame around the occupied area of the original Ops. The occupied
        area includes all points from line_to and close_path commands.
        """
        occupied_points = []
        last_point = None
        for cmd in self.commands:
            if cmd.is_travel_command():
                last_point = cmd.args
            elif cmd.is_cutting_command():
                x, y = cmd.args[:2]
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
        for cmd in self.commands:
            if cmd.is_travel_command():
                if last is not None:
                    total += math.dist(cmd.args, last)
                last = cmd.args
            elif cmd.is_cutting_command():
                # treating arcs as lines is probably good enough
                if last is not None:
                    total += math.dist(cmd.args[:2], last)
                last = cmd.args[:2]
        return total

    def cut_distance(self):
        """
        Like distance(), but only counts cut distance.
        """
        total = 0.0

        last = None
        for cmd in self.commands:
            if cmd.is_travel_command():
                last = cmd.args
            elif cmd.is_cutting_command():
                # treating arcs as lines is probably good enough
                if last is not None:
                    total += math.dist(cmd.args[:2], last)
                last = cmd.args[:2]
        return total

    def segments(self):
        segment = []
        for command in self.commands:
            if not segment:
                segment.append(command)
                continue

            if command.is_travel_command():
                yield segment
                segment = [command]

            elif command.is_cutting_command():
                segment.append(command)

            elif command.is_state_command():
                yield segment
                yield [command]
                segment = []

        if segment:
            yield segment

    def dump(self):
        for segment in self.segments():
            print(segment)
