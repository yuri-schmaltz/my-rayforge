import math
import pytest
import numpy as np
from rayforge.opstransformer.arcwelder.points import remove_duplicates, \
                                                     are_colinear, \
                                                     is_clockwise, \
                                                     arc_direction, \
                                                     fit_circle, \
                                                     arc_to_polyline_deviation


def test_remove_duplicates():
    segment = [(1,1), (1,1), (2,2), (2,2)]
    assert remove_duplicates(segment) == [(1,1), (2,2)]

def test_are_colinear():
    # Colinear points (horizontal)
    points = [(0, 0), (5, 0), (10, 0)]
    assert are_colinear(points) == True

    # Colinear points (vertical)
    points = [(0, 0), (0, 5), (0, 10)]
    assert are_colinear(points) == True

    # Non-colinear points
    points = [(0, 0), (1, 1), (2, 2.1)]
    assert are_colinear(points) == False

def test_is_clockwise():
    # Clockwise points (right half-circle)
    points = [(0, 0), (1, 1), (2, 0)]
    assert is_clockwise(points) == True

    # Counter-clockwise points (left half-circle)
    points = [(0, 0), (-1, 1), (-2, 0)]
    assert is_clockwise(points) == False

def test_arc_direction_clockwise_half_circle():
    """Test a semicircle moving clockwise."""
    center = (0, 0)
    points = [
        (1, 0),          # 0 radians
        (0, -1),         # -π/2 (or 3π/2)
        (-1, 0),         # π radians (unwrapped to -π)
    ]
    assert arc_direction(points, center) is True

def test_arc_direction_counter_clockwise_half_circle():
    """Test a semicircle moving counter-clockwise."""
    center = (0, 0)
    points = [
        (1, 0),          # 0 radians
        (0, 1),          # π/2
        (-1, 0),         # π
    ]
    assert arc_direction(points, center) is False

def test_arc_direction_clockwise_full_circle():
    """Test a full clockwise circle."""
    center = (0, 0)
    points = [
        (1, 0),
        (0, -1),
        (-1, 0),
        (0, 1),
        (1, 0),
    ]
    assert arc_direction(points, center) is True

def test_arc_direction_counter_clockwise_full_circle():
    """Test a full counter-clockwise circle."""
    center = (0, 0)
    points = [
        (1, 0),
        (0, 1),
        (-1, 0),
        (0, -1),
        (1, 0),
    ]
    assert arc_direction(points, center) is False

def test_arc_direction_minimal_clockwise_arc():
    """Test a minimal 3-point clockwise arc."""
    center = (0, 0)
    points = [
        (2, 0),
        (1, -1),
        (0, 0),
    ]
    assert arc_direction(points, center) is True

def test_arc_direction_minimal_counter_clockwise_arc():
    """Test a minimal 3-point counter-clockwise arc."""
    center = (0, 0)
    points = [
        (2, 0),
        (1, 1),
        (0, 0),
    ]
    assert arc_direction(points, center) is False

def test_arc_direction_crossing_angle_discontinuity_counter_clockwise():
    """Test an arc crossing the π/-π discontinuity (counter-clockwise)."""
    center = (0, 0)
    points = [
        (1, 0.1),        # ~0 radians
        (0, 1),          # π/2
        (-1, 0.1),       # ~π radians (unwrapped to -π)
    ]
    assert arc_direction(points, center) is False

def test_arc_direction_small_radius_arc():
    """Test a small-radius clockwise arc."""
    center = (1, 1)
    points = [
        (1.1, 1),
        (1, 0.9),
        (0.9, 1),
    ]
    assert arc_direction(points, center) is True

def test_fit_circle_collinear_returns_none():
    """Test collinear points return None."""
    points = [(0, 0), (2, 2), (5, 5)]
    assert fit_circle(points) is None

def test_fit_circle_perfect_circle():
    """Test perfect circle fitting."""
    center = (2, 3)
    radius = 5
    angles = np.linspace(0, 2*np.pi, 20)
    points = [
        (center[0] + radius * np.cos(theta),
        center[1] + radius * np.sin(theta)
        ) for theta in angles
    ]
    result = fit_circle(points)
    assert result is not None

    (xc, yc), r, error = result
    assert xc == pytest.approx(center[0], abs=1e-6)
    assert yc == pytest.approx(center[1], abs=1e-6)
    assert r == pytest.approx(radius, abs=1e-6)
    assert error < 1e-6

def test_fit_circle_noisy_circle():
    """Test circle fitting with noisy points."""
    center = (-1, 4)
    radius = 3
    np.random.seed(42)  # For reproducibility
    angles = np.linspace(0, 2*np.pi, 30)
    noise = np.random.normal(scale=0.1, size=(len(angles), 2))

    points = [
        (center[0] + radius * np.cos(theta) + dx,
         center[1] + radius * np.sin(theta) + dy
        ) for (theta, (dx, dy)) in zip(angles, noise)
    ]
    result = fit_circle(points)
    assert result is not None

    (xc, yc), r, error = result
    assert xc == pytest.approx(center[0], abs=0.15)
    assert yc == pytest.approx(center[1], abs=0.15)
    assert r == pytest.approx(radius, abs=0.15)
    assert error < 0.2

def test_fit_circle_insufficient_points():
    """Test 1-2 points or duplicates return None."""
    assert fit_circle([(0, 0)]) is None
    assert fit_circle([(1, 2), (3, 4)]) is None
    assert fit_circle([(5, 5), (5, 5), (5, 5)]) is None

def test_fit_circle_small_radius():
    """Test small-radius circle fitting."""
    center = (0, 0)
    radius = 0.1
    angles = np.linspace(0, 2*np.pi, 10)
    points = [
        (center[0] + radius * np.cos(theta),
        center[1] + radius * np.sin(theta)
        ) for theta in angles
    ]
    result = fit_circle(points)
    assert result is not None

    (xc, yc), r, error = result
    assert r == pytest.approx(radius, rel=0.01)

def test_fit_circle_nearly_collinear_but_valid():
    """Test near-colinear points that still form a valid circle."""
    points = [(0, 0), (1, 0), (2, 0.2)]  # Area = 0.2 (>1e-3 threshold)
    result = fit_circle(points)
    assert result is not None  # Should attempt to fit

    (xc, yc), r, error = result
    assert error < 1.0  # Large error expected, but still returns a circle

def test_fit_circle_horizontal_line_fails():
    """Test horizontal line (collinear) returns None."""
    points = [(0, 0), (1, 0), (2, 0)]
    assert fit_circle(points) is None

def test_fit_circle_semicircle_accuracy():
    """Verify fit_circle() returns correct parameters for a perfect semicircle"""
    center = (5, 0)
    radius = 10.0
    num_points = 20

    # Generate semicircle points (180 degrees)
    angles = np.linspace(0, np.pi, num_points)
    points = [
        (center[0] + radius * np.cos(theta),
         center[1] + radius * np.sin(theta))
        for theta in angles
    ]

    # Fit circle
    result = fit_circle(points)
    assert result is not None, "Failed to fit semicircle"

    (xc, yc), r, error = result

    # Validate center coordinates (should match real center (5,0))
    assert np.isclose(xc, 5.0, atol=0.001), \
        f"Center X error: {xc:.3f} != 5.000"
    assert np.isclose(yc, 0.0, atol=0.001), \
        f"Center Y error: {yc:.3f} != 0.000"

    # Validate radius
    assert np.isclose(r, 10.0, rtol=0.001), \
        f"Radius error: {r:.3f} != 10.000"

    # Validate maximum deviation
    assert error < 1e-6, \
        f"Fitting error too large: {error:.6f}"

def test_fit_circle_partial_arc_accuracy():
    """Verify fit_circle() accuracy for a 90-degree arc offset from the centroid"""
    center = (7, 3)
    radius = 5.0
    # Generate points along a 90-degree arc (π/2 to π radians)
    angles = np.linspace(np.pi/2, np.pi, 50)
    points = [
        (center[0] + radius * np.cos(theta),
         center[1] + radius * np.sin(theta))
        for theta in angles
    ]

    # Fit circle
    result = fit_circle(points)
    assert result is not None, "Failed to fit partial arc"

    (xc, yc), r, error = result

    # Validate center (true center is (7,3))
    assert np.isclose(xc, 7.0, atol=0.01), f"Center X: {xc:.3f} ≠ 7.0"
    assert np.isclose(yc, 3.0, atol=0.01), f"Center Y: {yc:.3f} ≠ 3.0"

    # Validate radius
    assert np.isclose(r, 5.0, rtol=0.01), f"Radius: {r:.3f} ≠ 5.0"

    # Validate error
    assert error < 0.05, f"Error too large: {error:.3f}mm"


def test_arc_to_polyline_deviation_perfect_arc():
    """Test deviation for a perfect 90-degree arc."""
    center = (7, 3)
    radius = 5.0
    angles = np.linspace(np.pi/2, np.pi, 10)
    points = [(center[0] + radius * np.cos(t), center[1] + radius * np.sin(t))
              for t in angles]
    deviation = arc_to_polyline_deviation(points, center, radius)
    assert deviation < 0.05, f"Deviation too large: {deviation}"


def test_arc_to_polyline_deviation_too_large():
    """Test deviation for a perfect 90-degree arc."""
    center = (7, 3)
    radius = 5.0
    angles = np.linspace(np.pi/2, np.pi, 5)
    points = [(center[0] + radius * np.cos(t), center[1] + radius * np.sin(t))
              for t in angles]
    deviation = arc_to_polyline_deviation(points, center, radius)
    assert deviation > 0.05, f"Expected larger deviation: {deviation}"


def test_arc_to_polyline_deviation_straight_line():
    """Test deviation for a straight line with a large-radius arc."""
    points = [(0, 0), (1, 0.01), (2, -0.01), (3, 0)]
    center = (1.5, 10)  # Large radius arc
    radius = 100.0
    deviation = arc_to_polyline_deviation(points, center, radius)
    assert deviation > 0.05, f"Deviation too small: {deviation}"


def test_arc_to_polyline_deviation_single_segment():
    """Test deviation for a single line segment."""
    points = [(0, 0), (1, 1)]
    center = (0.5, 0.5)
    radius = math.sqrt(0.5)
    deviation = arc_to_polyline_deviation(points, center, radius)
    assert deviation < 1.0, f"Deviation too large: {deviation}"
