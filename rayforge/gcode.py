class GCodeSerializer:
    """Serializes a WorkStep to G-code."""
    def __init__(self, machine):
        self.machine = machine
        gcode = []+self.machine.preamble
        self.is_cutting = False
        self.air_assist = False

    def laser_on(self, gcode, workstep):
        if not self.is_cutting:
            gcode.append(f"M4 S{workstep.power}")
            self.is_cutting = True
        if workstep.air_assist and not self.air_assist:
            gcode.append(self.machine.air_assist_on or "")
            self.air_assist = True

    def laser_off(self, gcode, workstep):
        if self.is_cutting:
            gcode.append("M5 ; Disable laser")
            self.is_cutting = False
        if self.air_assist:
            gcode.append(self.machine.air_assist_off or "")
            self.air_assist = False

    def finish_step(self, gcode, workstep):
        self.laser_off(gcode, workstep)

    def finish(self, gcode, workstep):
        self.laser_off(gcode, workstep)
        gcode += self.machine.postscript

    def move_to(self, gcode, workstep, x, y):
        self.laser_off(gcode, workstep)
        gcode.append(f"G0 X{x:.3f} Y{y:.3f} F{workstep.travel_speed}")

    def line_to(self, gcode, workstep, x, y):
        self.laser_on(gcode, workstep)
        gcode.append(f"G1 X{x:.3f} Y{y:.3f} F{workstep.cut_speed}")

    def close_path(self, gcode, workstep, start_x, start_y):
        self.line_to(gcode, workstep, start_x, start_y)  # Ensure path is closed

    def _serialize_workstep(self, gcode, workstep):
        laser = workstep.laser
        assert workstep.power <= laser.max_power
        assert workstep.cut_speed <= self.machine.max_cut_speed
        assert workstep.travel_speed <= self.machine.max_travel_speed

        workstep.path.optimize()
        step_gcode = []
        start_x, start_y = None, None
        for command, *args in workstep.path.commands:
            if command == 'move_to':
                start_x, start_y = args

            elif command == 'close_path' and start_x is not None:
                self.close_path(step_gcode, workstep, start_x, start_y)
                continue

            op = getattr(self, command)
            op(step_gcode, workstep, *args)

        for thepass in range(workstep.passes):
            gcode.append(f"; Pass {thepass+1}")
            gcode += step_gcode
        self.finish_step(gcode, workstep)

    def serialize_workplan(self, workplan):
        gcode = []+self.machine.preamble
        for step in workplan:
            gcode.append(f"; Starting step: {step.name}")
            self._serialize_workstep(gcode, step)
        self.finish(gcode, None)
        return "\n".join(gcode)
