import numpy as np
import math


# Split a single Path’s commands into segments.
# Needed for the path optimization algorithm.
def split_segments(path):
    segments = []
    current = []
    closed = False
    for cmd in path.commands:
        if cmd[0] == 'move_to':
            if current:
                segments.append({'pts': current, 'closed': closed})
            current = [(cmd[1], cmd[2])]
            closed = False
        elif cmd[0] == 'line_to':
            current.append((cmd[1], cmd[2]))
        elif cmd[0] == 'close_path':
            closed = True
            if current and current[0] != current[-1]:
                current.append(current[0])
            segments.append({'pts': current, 'closed': True})
            current, closed = [], False
    if current:
        segments.append({'pts': current, 'closed': closed})
    return segments

# Greedy ordering using vectorized math.dist computations.
# Needed for the path optimization algorithm.
def greedy_order_segments(segments):
    if not segments:
        return []
    ordered = []
    current_seg = segments[0]
    ordered.append(current_seg)
    current_point = np.array(current_seg['pts'][-1])
    remaining = segments[1:]
    while remaining:
        starts = np.array([seg['pts'][0] for seg in remaining])
        ends   = np.array([seg['pts'][-1] for seg in remaining])
        d_starts = np.linalg.norm(starts - current_point, axis=1)
        d_ends   = np.linalg.norm(ends - current_point, axis=1)
        candidate_dists = np.minimum(d_starts, d_ends)
        best_idx = int(np.argmin(candidate_dists))
        best_seg = remaining.pop(best_idx)
        # Flip candidate if its end is closer.
        if d_ends[best_idx] < d_starts[best_idx]:
            best_seg = best_seg.copy()
            best_seg['pts'] = list(reversed(best_seg['pts']))
        ordered.append(best_seg)
        current_point = np.array(best_seg['pts'][-1])
    return ordered

# Try flipping each segment if doing so lowers the sum of the incoming
# and outgoing travel.
# Needed for the path optimization algorithm.
def flip_improvement(ordered):
    improved = True
    while improved:
        improved = False
        for i in range(1, len(ordered)):
            prev_pt = ordered[i-1]['pts'][-1]
            pts = ordered[i]['pts']
            cost = math.dist(prev_pt, pts[0])
            if i < len(ordered)-1:
                cost += math.dist(pts[-1], ordered[i+1]['pts'][0])
            flipped = list(reversed(pts))
            flipped_cost = math.dist(prev_pt, flipped[0])
            if i < len(ordered)-1:
                flipped_cost += math.dist(flipped[-1], ordered[i+1]['pts'][0])
            if flipped_cost < cost:
                ordered[i]['pts'] = flipped
                improved = True
    return ordered

# 2-opt: try reversing entire sub-sequences if that lowers the travel cost.
# Needed for the path optimization algorithm.
def two_opt(ordered, max_iter=1000):
    n = len(ordered)
    if n < 3:
        return ordered
    iter_count = 0
    improved = True
    while improved and iter_count < max_iter:
        improved = False
        for i in range(n - 2):
            for j in range(i+2, n):
                A_end = ordered[i]['pts'][-1]
                B_start = ordered[i+1]['pts'][0]
                E_end = ordered[j]['pts'][-1]
                if j < n - 1:
                    F_start = ordered[j+1]['pts'][0]
                    curr_cost = math.dist(A_end, B_start) + math.dist(E_end, F_start)
                    new_cost = math.dist(A_end, E_end) + math.dist(ordered[i+1]['pts'][0], F_start)
                else:
                    curr_cost = math.dist(A_end, B_start)
                    new_cost = math.dist(A_end, E_end)
                if new_cost < curr_cost:
                    sub = ordered[i+1:j+1]
                    # Reverse order and flip each segment.
                    for seg in sub:
                        seg['pts'] = list(reversed(seg['pts']))
                    ordered[i+1:j+1] = sub[::-1]
                    improved = True
        iter_count += 1
    return ordered


class Path:
    """
    Represents a set of generated paths that are used for
    making gcode, but also to generate vector graphics for display.
    """
    def __init__(self):
        self.commands = []

    def clear(self):
        self.commands = []

    def move_to(self, x, y):
        self.commands.append(('move_to', float(x), float(y)))

    def line_to(self, x, y):
        self.commands.append(('line_to', float(x), float(y)))

    def close_path(self):
        self.commands.append(('close_path',))

    def set_color(self, r: float, g: float, b: float):
        """Cairo-compatible RGB (0.0-1.0 floats)"""
        self.commands.append(('set_color', (r, g, b)))

    def set_power(self, power: float):
        """Laser power (0-1000 for GRBL)"""
        self.commands.append(('set_power', float(power)))

    def set_travel_speed(self, speed: float):
        """Rapid movement speed (mm/min)"""
        self.commands.append(('set_travel_speed', float(speed)))

    def enable_air_assist(self):
        self.commands.append(('enable_air_assist',))

    def disable_air_assist(self):
        self.commands.append(('disable_air_assist',))

    def optimize(self, max_iter=1000):
        """
        Uses the 2-opt swap algorithm to address the Traveline Salesman Problem
        to minimize travel moves in the GCode.
        """
        segments = split_segments(self)
        ordered = greedy_order_segments(segments)
        ordered = flip_improvement(ordered)
        ordered = two_opt(ordered, max_iter=max_iter)

        # Reassemble the path.
        self.commands = []
        for seg in ordered:
            pts = seg['pts']
            if not pts:
                continue
            self.move_to(*pts[0])
            for pt in pts[1:]:
                self.line_to(*pt)
            if seg['closed']:
                self.close_path()

    def distance(self):
        """
        Calculates the total distance of all moves. Mostly exists to help
        debug the optimize() method.
        """
        total = 0.0

        start = 0, 0
        last = None
        for op, *args in self.commands:
            if op == 'move_to':
                if last is not None:
                    total += math.dist(args, last)
                last = args
                start = args
            elif op == 'line_to':
                if last is not None:
                    total += math.dist(args, last)
                last = args
            elif cmd[0] == 'close_path':
                if start is not None:
                    total += math.dist(start, last)
                last = start
        return total

    def dump(self):
        print(self.commands)
