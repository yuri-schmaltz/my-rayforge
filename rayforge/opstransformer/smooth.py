import math
from ..models.ops import Ops, LineToCommand, MoveToCommand
from .transformer import OpsTransformer
from .arcwelder.points import remove_duplicates


class Smooth(OpsTransformer):
    """
    Smooths the points in an Ops object using a moving average to
    reduce noise.
    """
    def __init__(self, smooth_window=5):
        """
        smooth_window: Number of points in the moving average window
        (odd preferred).
        """
        self.smooth_window = max(1, smooth_window)  # Ensure at least 1

    def run(self, ops: Ops):
        segments = list(ops.segments())
        ops.clear()

        for segment in segments:
            if self._is_line_only_segment(segment):
                # Smooth pure LineToCommand segments
                smoothed_points = self._smooth_segment([cmd.end for cmd in segment])
                ops.move_to(*smoothed_points[0])
                for point in smoothed_points[1:]:
                    ops.line_to(*point)
            else:
                # Preserve mixed segments, arcs, or non-cutting commands
                for command in segment:
                    ops.add(command)

    def _is_line_only_segment(self, segment):
        """
        Check if the segment is a MoveTo followed by only LineToCommands.
        """
        if len(segment) <= 1:
            return False
        if not isinstance(segment[0], MoveToCommand):
            return False
        return all(isinstance(cmd, LineToCommand)
                   for cmd in segment[1:])

    def _smooth_segment(self, points):
        """Apply a moving average to smooth the points."""
        if len(points) < 3 or self.smooth_window <= 1:
            return remove_duplicates(points)

        half_window = (self.smooth_window - 1) // 2
        smoothed = []

        for i in range(len(points)):
            start = max(0, i - half_window)
            end = min(len(points), i + half_window + 1)
            window = points[start:end]
            avg_x = sum(p[0] for p in window) / len(window)
            avg_y = sum(p[1] for p in window) / len(window)
            smoothed.append((avg_x, avg_y))

        return smoothed
