from ..models.ops import Ops, \
                         Command, \
                         SetPowerCommand, \
                         SetCutSpeedCommand, \
                         SetTravelSpeedCommand, \
                         EnableAirAssistCommand, \
                         DisableAirAssistCommand, \
                         MoveToCommand, \
                         LineToCommand, \
                         ArcToCommand
from ..models.machine import Machine
from .encoder import OpsEncoder


class GcodeEncoder(OpsEncoder):
    """Converts Ops commands to G-code using instance state tracking"""
    def __init__(self):
        self.power = None             # Current laser power (None = off)
        self.cut_speed = None         # Current cutting speed (mm/min)
        self.travel_speed = None      # Current travel speed (mm/min)
        self.air_assist = False       # Air assist state
        self.laser_active = False     # Laser on/off state

    def encode(self, ops: Ops, machine: Machine) -> str:
        """Main encoding workflow"""
        gcode = []+machine.preamble
        for cmd in ops:
            self._handle_command(gcode, cmd, machine)
        self._finalize(gcode, machine)
        return '\n'.join(gcode)

    def _handle_command(self, gcode: list, cmd: Command, machine: Machine):
        """Dispatch command to appropriate handler"""
        match cmd:
            case SetPowerCommand():
                self._update_power(gcode, cmd.power, machine)
            case SetCutSpeedCommand():
                # We limit to max travel speed, not max cut speed, to
                # allow framing operations to go faster. Cut limits should
                # should be kept by ensuring an Ops object is created
                # with limits in mind.
                self.cut_speed = min(cmd.speed, machine.max_travel_speed)
            case SetTravelSpeedCommand():
                self.travel_speed = min(cmd.speed, machine.max_travel_speed)
            case EnableAirAssistCommand():
                self._set_air_assist(gcode, True, machine)
            case DisableAirAssistCommand():
                self._set_air_assist(gcode, False, machine)
            case MoveToCommand():
                self._handle_move_to(gcode, *cmd.end)
            case LineToCommand():
                self._handle_line_to(gcode, *cmd.end)
            case ArcToCommand():
                self._handle_arc_to(gcode,
                                    *cmd.end,
                                    *cmd.center_offset,
                                    cmd.clockwise)

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

    def _handle_move_to(self, gcode: list, x: float, y: float):
        """Rapid movement with laser safety"""
        self._laser_off(gcode)
        cmd = f"G0 X{x:.3f} Y{y:.3f}"
        if self.travel_speed:
            cmd += f" F{self.travel_speed}"
        gcode.append(cmd)

    def _handle_line_to(self, gcode: list, x: float, y: float):
        """Cutting movement with laser activation"""
        self._laser_on(gcode)
        cmd = f"G1 X{x:.3f} Y{y:.3f}"
        if self.cut_speed:
            cmd += f" F{self.cut_speed}"
        gcode.append(cmd)

    def _handle_arc_to(self,
                       gcode: list,
                       x: float,
                       y: float,
                       i: float,
                       j: float,
                       clockwise: bool):
        """Cutting movement with laser activation"""
        self._laser_on(gcode)
        cmd = "G2" if clockwise else "G3"
        cmd += f" X{x:.3f} Y{y:.3f} I{i:.3f} J{j:.3f}"
        if self.cut_speed:
            cmd += f" F{self.cut_speed}"
        gcode.append(cmd)

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
