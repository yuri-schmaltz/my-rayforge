from ..models.path import Path
from ..models.machine import Machine
from .encoder import PathEncoder


class GcodeEncoder(PathEncoder):
    """Converts Path commands to G-code using instance state tracking"""
    def __init__(self):
        self.power = None             # Current laser power (None = off)
        self.cut_speed = None         # Current cutting speed (mm/min)
        self.travel_speed = None      # Current travel speed (mm/min)
        self.air_assist = False       # Air assist state
        self.laser_active = False     # Laser on/off state
        self.position = (None, None)  # Last known coordinates

    def encode(self, path: Path, machine: Machine) -> str:
        """Main encoding workflow"""
        gcode = []+machine.preamble
        for cmd in path.commands:
            self._handle_command(gcode, cmd, machine)
        self._finalize(gcode, machine)
        return '\n'.join(gcode)

    def _handle_command(self, gcode: list, cmd: tuple, machine: Machine):
        """Dispatch command to appropriate handler"""
        match cmd:
            case ('set_power', power):
                self._update_power(gcode, power, machine)
            case ('set_cut_speed', speed):
                self.cut_speed = min(speed, machine.max_cut_speed)
            case ('set_travel_speed', speed):
                self.travel_speed = min(speed, machine.max_travel_speed)
            case 'enable_air_assist':
                self._set_air_assist(gcode, True, machine)
            case 'disable_air_assist':
                self._set_air_assist(gcode, False, machine)
            case ('move_to', x, y):
                self._handle_move(gcode, x, y)
            case ('line_to', x, y):
                self._handle_cut(gcode, x, y)
            case ('close_path',):
                self._close_path(gcode)

    def _update_power(self, gcode: list, power: float, machine: Machine):
        """Update laser power and toggle state if needed"""
        self.power = min(power, machine.heads[0].max_power)
        if self.laser_active and self.power <= 0:
            self._laser_off(gcode)
        elif not self.laser_active and self.power > 0:
            self._laser_on(gcode)

    def _set_air_assist(self, gcode: list, state: bool, machine: Machine):
        """Update air assist state with machine commands"""
        if self.air_assist == state:
            return
        self.air_assist = state
        cmd = machine.air_assist_on if state else machine.air_assist_off
        if cmd:
            gcode.append(cmd)

    def _handle_move(self, gcode: list, x: float, y: float):
        """Rapid movement with laser safety"""
        self._laser_off(gcode)
        gcode.append(f"G0 X{x:.3f} Y{y:.3f} F{self.travel_speed}")
        self.position = (x, y)

    def _handle_cut(self, gcode: list, x: float, y: float):
        """Cutting movement with laser activation"""
        self._laser_on(gcode)
        gcode.append(f"G1 X{x:.3f} Y{y:.3f} F{self.cut_speed}")
        self.position = (x, y)

    def _close_path(self, gcode: list):
        """Close path by returning to start position"""
        if self.position != (None, None) and self.laser_active:
            start_x, start_y = self.position
            self._handle_cut(gcode, start_x, start_y)

    def _laser_on(self, gcode: list):
        """Activate laser if not already on"""
        if not self.laser_active and self.power:
            gcode.append(f"M4 S{self.power:.0f}")
            self.laser_active = True

    def _laser_off(self, gcode: list):
        """Deactivate laser if active"""
        if self.laser_active:
            gcode.append("M5")
            self.laser_active = False

    def _finalize(self, gcode: list, machine: Machine):
        """Cleanup at end of file"""
        self._laser_off(gcode)
        if self.air_assist:
            gcode.append(machine.air_assist_off or "")
        gcode.extend(machine.postscript)
        gcode.append('')
