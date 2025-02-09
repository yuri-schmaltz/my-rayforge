class GCodeSerializer:
    """Serializes a WorkStep to G-code."""
    def __init__(self, machine):
        self.machine = machine
        self.gcode = []+self.machine.preamble
        self.is_cutting = False
        self.air_assist = False

    def laser_on(self, workstep):
        if not self.is_cutting:
            self.gcode.append(f"M4 S{workstep.power}")
            self.is_cutting = True
        if workstep.air_assist and not self.air_assist:
            self.gcode.append(self.machine.air_assist_on or "")
            self.air_assist = True

    def laser_off(self, workstep):
        if self.is_cutting:
            self.gcode.append("M5 ; Disable laser")
            self.is_cutting = False
        if self.air_assist:
            self.gcode.append(self.machine.air_assist_off or "")
            self.air_assist = False

    def finish_step(self, workstep):
        self.laser_off(workstep)

    def finish(self, workstep):
        self.laser_off(workstep)
        self.gcode += self.machine.postscript

    def move_to(self, workstep, x, y):
        self.laser_off(workstep)
        self.gcode.append(f"G0 X{x:.3f} Y{y:.3f} F{workstep.travel_speed}")

    def line_to(self, workstep, x, y):
        self.laser_on(workstep)
        self.gcode.append(f"G1 X{x:.3f} Y{y:.3f} F{workstep.cut_speed}")

    def close_path(self, workstep, start_x, start_y):
        self.line_to(workstep, start_x, start_y)  # Ensure path is closed

    def _serialize_workstep(self, workstep):
        laser = workstep.laser
        assert workstep.power <= laser.max_power
        assert workstep.cut_speed <= self.machine.max_cut_speed
        assert workstep.travel_speed <= self.machine.max_travel_speed
        start_x, start_y = None, None
        for command, *args in workstep.path.paths:
            if command == 'move_to':
                start_x, start_y = args

            elif command == 'close_path' and start_x is not None:
                self.close_path(workstep, start_x, start_y)
                continue

            op = getattr(self, command)
            op(workstep, *args)
        self.finish_step(workstep)
        return "\n".join(self.gcode)

    def serialize_workplan(self, workplan):
        for step in workplan:
            self.gcode.append(f"; Starting step: {step.name}")
            self._serialize_workstep(step)
        self.finish(None)
        return "\n".join(self.gcode)
