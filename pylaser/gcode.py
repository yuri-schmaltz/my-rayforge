class GCodeSerializer:
    """Serializes PathDOM to G-code."""
    def __init__(self, laser_power=1000, travel_speed=3000, cut_speed=1000):
        self.laser_power = laser_power  # Max power (0-1000 for GRBL)
        self.travel_speed = travel_speed  # Travel speed (mm/min)
        self.cut_speed = cut_speed  # Cutting speed (mm/min)
        self.gcode = ["G21 ; Set units to mm", "G90 ; Absolute positioning"]
        self.is_cutting = False
    
    def laser_on(self):
        self.gcode.append(f"M4 S{self.laser_power}")
        self.is_cutting = True
    
    def laser_off(self):
        self.gcode.append("M5 ; Disable laser")
        self.is_cutting = False
    
    def finish(self):
        self.laser_off()
        self.gcode.append("G0 X0 Y0 ; Return to origin")

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
