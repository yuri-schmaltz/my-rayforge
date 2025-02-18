import math

"""
THIS FILE IS CURRENTLY DYSFUNCT AND UNUSED. WILL BE RESTORED TO A WORKING MODIFIER IN THE FUTURE
"""

def compute_circle(p1, p2, p3):
    """Return (cx, cy, r) for the circle through p1, p2, p3.
    Returns None if the points are collinear."""
    (x1, y1), (x2, y2), (x3, y3) = p1, p2, p3
    d = 2 * (x1*(y2-y3) + x2*(y3-y1) + x3*(y1-y2))
    if abs(d) < 1e-6:
        return None  # Collinear
    ux = ((x1**2 + y1**2)*(y2-y3) + (x2**2 + y2**2)*(y3-y1) + (x3**2 + y3**2)*(y1-y2)) / d
    uy = ((x1**2 + y1**2)*(x3-x2) + (x2**2 + y2**2)*(x1-x3) + (x3**2 + y3**2)*(x2-x1)) / d
    r = math.hypot(x1-ux, y1-uy)
    return (ux, uy, r)

def point_on_circle(circle, point, tol):
    """Check if the point is within tol of the circle's radius."""
    cx, cy, r = circle
    return abs(math.hypot(point[0]-cx, point[1]-cy) - r) <= tol

def arc_direction(p_start, p_mid, p_end):
    """Return 'G2' for CW or 'G3' for CCW based on the cross product."""
    # Compute the cross product (p_mid - p_start) x (p_end - p_start)
    (x1, y1), (x2, y2), (x3, y3) = p_start, p_mid, p_end
    cross = (x2 - x1) * (y3 - y1) - (y2 - y1) * (x3 - x1)
    return "G3" if cross > 0 else "G2"

def arcwelder(waypoints, tolerance=0.1, speed=1000):
    """
    Takes a list of waypoints [(x,y), ...] that were originally G0/G1 moves and returns
    a list of G-code commands that use arcs (G2/G3) where possible.
    
    If an arc cannot be fit (e.g. points are collinear or exceed the tolerance),
    the function falls back to linear moves (G1).
    """
    if not waypoints:
        return []
    
    gcode = []
    i = 0
    # Always move rapidly to the first point.
    gcode.append(f"G0 X{waypoints[0][0]:.3f} Y{waypoints[0][1]:.3f}")
    
    while i < len(waypoints) - 1:
        # Try to form an arc with at least three points.
        if i + 2 < len(waypoints):
            p_start = waypoints[i]
            p_mid = waypoints[i+1]
            p_third = waypoints[i+2]
            circle = compute_circle(p_start, p_mid, p_third)
            if circle is None:
                # Points are collinear: use a linear move.
                gcode.append(f"G1 X{p_mid[0]:.3f} Y{p_mid[1]:.3f} F{speed}")
                i += 1
                continue

            # Now extend the arc as far as possible.
            j = i + 2
            while j < len(waypoints) and point_on_circle(circle, waypoints[j], tolerance):
                j += 1
            # j is now one past the last point that fits the arc.
            p_end = waypoints[j-1]
            cx, cy, r = circle
            # Calculate I and J relative to p_start.
            I = cx - p_start[0]
            J = cy - p_start[1]
            cmd = arc_direction(p_start, p_mid, p_end)
            gcode.append(f"{cmd} X{p_end[0]:.3f} Y{p_end[1]:.3f} I{I:.3f} J{J:.3f} F{speed}")
            i = j - 1
        else:
            # Fewer than 3 points remain; do a linear move.
            i += 1
            p = waypoints[i]
            gcode.append(f"G1 X{p[0]:.3f} Y{p[1]:.3f} F{speed}")
    
    return gcode

# Example usage:
if __name__ == "__main__":
    # A sample set of waypoints that roughly lie on an arc.
    waypoints = [
        (0, 0),
        (5, 2),
        (10, 0),
        (15, -2),
        (20, 0)
    ]
    commands = arcwelder(waypoints, tolerance=0.2, speed=1200)
    for cmd in commands:
        print(cmd)
