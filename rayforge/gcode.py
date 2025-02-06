class GCodeSerializer:
    """Serializes a Path model to G-code."""
    def __init__(self, machine):
        self.machine = machine
        self.power = self.machine.heads[0].max_power
        self.travel_speed = self.machine.max_travel_speed
        self.cut_speed = self.machine.max_cut_speed
        self.gcode = []+self.machine.preamble
        self.is_cutting = False

    def laser_on(self):
        if not self.is_cutting:
            self.gcode.append(f"M4 S{self.power}")
        self.is_cutting = True

    def laser_off(self):
        if self.is_cutting:
            self.gcode.append("M5 ; Disable laser")
        self.is_cutting = False

    def finish(self):
        self.laser_off()
        self.gcode += self.machine.postscript

    def move_to(self, x, y):
        self.laser_off()
        self.gcode.append(f"G0 X{x:.3f} Y{y:.3f} F{self.travel_speed}")

    def line_to(self, x, y):
        if not self.is_cutting:
            self.laser_on()
        self.gcode.append(f"G1 X{x:.3f} Y{y:.3f} F{self.cut_speed}")

    def close_path(self, start_x, start_y):
        self.line_to(start_x, start_y)  # Ensure path is closed
        self.laser_off()

    def serialize(self, path_dom):
        start_x, start_y = None, None
        for command, *args in path_dom.paths:
            if command == 'move_to':
                start_x, start_y = args

            elif command == 'close_path' and start_x is not None:
                self.close_path(start_x, start_y)
                continue

            op = getattr(self, command)
            op(*args)

        self.finish()
        return "\n".join(self.gcode)
