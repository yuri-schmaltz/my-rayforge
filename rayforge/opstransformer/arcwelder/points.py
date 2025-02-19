import math
import numpy as np
from scipy.optimize import least_squares
from itertools import groupby


def remove_duplicates(segment):
    """
    Removes *consecutive* duplicates from a list of points.
    """
    return [k for (k, v) in groupby(segment)]


def are_colinear(points):
    """
    Colinearity check with relaxed threshold
    """
    if len(points) < 3:
        return True
        
    p1, p2, p3 = points[0], points[1], points[2]
    area = abs((p2[0]-p1[0])*(p3[1]-p1[1])
             - (p2[1]-p1[1])*(p3[0]-p1[0]))
    return area < 1e-3


def is_clockwise(points):
    """
    Determines direction using cross product.
    """
    if len(points) < 3:
        return False
    
    p1, p2, p3 = points[0], points[1], points[2]
    cross = ((p2[0]-p1[0])*(p3[1]-p2[1])
           - (p2[1]-p1[1])*(p3[0]-p2[0]))
    return cross < 0


def arc_direction(points, center):
    xc, yc = center
    cross_sum = 0.0
    for i in range(len(points) - 1):
        x0, y0 = points[i]
        x1, y1 = points[i + 1]
        dx0 = x0 - xc
        dy0 = y0 - yc
        dx1 = x1 - xc
        dy1 = y1 - yc
        cross = dx0 * dy1 - dy0 * dx1
        cross_sum += cross
    return cross_sum < 0  # True for clockwise


def fit_circle(points):
    """
    Attempts to fit a circle along the given points.
    Returns a tuple(center, radius, error) if successful.
    Returns None if points are colinear.
    """
    # Fast colinearity check first
    if len(points) < 3 or are_colinear(points):
        return None

    x = np.array([p[0] for p in points])
    y = np.array([p[1] for p in points])

    # Simplified initial guess
    x0, y0 = np.mean(x), np.mean(y)
    r0 = np.mean(np.sqrt((x-x0)**2 + (y-y0)**2))

    # Fit a circle.
    func = lambda p: np.sqrt((x-p[0])**2 + (y-p[1])**2) - p[2]
    result = least_squares(func, [x0, y0, r0], method='lm')
    xc, yc, r = result.x

    # Calculate the maximum deviation.
    error = np.max(np.abs(np.sqrt((x-xc)**2 + (y-yc)**2) - r))

    return (xc, yc), r, error
