import math
import numpy as np
from rayforge.models.ops import Ops, Command
from rayforge.opstransformer.arcwelder import ArcWeld
from rayforge.opstransformer.arcwelder.points import fit_circle

def test_arc_welder_converts_semicircle():
    """Test if ArcWelder correctly converts line segments into a semicircular arc."""
    # Create a semicircle using line segments
    ops = Ops()
    center = 0, 0
    radius = 10.0
    num_points = 20  # Generate 20 points along the semicircle
    
    # Generate points on a semicircle (180 degrees)
    angles = np.linspace(0, np.pi, num_points)
    points = [
        (center[0] + radius * np.cos(theta),
         center[1] + radius * np.sin(theta))
        for theta in angles
    ]
    
    # Build path
    ops.move_to(*points[0])
    for p in points[1:]:
        ops.line_to(*p)
    
    # Process with ArcWelder
    welder = ArcWeld(tolerance=0.1, min_points=3)
    welder.run(ops)
    
    # Verify arc generation
    arc_commands = [cmd for cmd in ops.commands if cmd.name == 'arc_to']
    assert len(arc_commands) == 1, "Should replace the entire segment with one arc"
    
    # Validate arc parameters
    arc = arc_commands[0]
    end_x, end_y, i, j, clockwise = arc.args
    
    # Check center offsets (I/J relative to start point (10,0))
    assert np.isclose(i, -10.0, atol=0.1), f"Expected I ≈ -10, got {i}"
    assert np.isclose(j, 0.0, atol=0.1), f"Expected J ≈ 0, got {j}"
    
    # Validate endpoint (-10,0)
    assert np.isclose(end_x, -10.0, atol=0.1), f"Expected X ≈ -10, got {end_x}"
    assert np.isclose(end_y, 0.0, atol=0.1), f"Expected Y ≈ 0, got {end_y}"
    
    # Validate direction (should be counter-clockwise for 180-degree arc)
    assert not clockwise, f"Expected CCW arc, got clockwise"

def test_arc_welder_ignores_straight_lines():
    """Test if ArcWelder leaves straight line segments unchanged."""
    ops = Ops()
    ops.move_to(10, 10)
    ops.line_to(11, 11)
    ops.line_to(12, 12)
    ops.line_to(13, 13)
    ops.line_to(14, 14)
    ops.line_to(15, 15)
    ops.line_to(16, 16)
    ops.line_to(17, 17)
    
    welder = ArcWeld(tolerance=0.1, min_points=3)
    welder.run(ops)
    
    # No arcs should be generated for colinear points
    assert all(cmd.name != 'arc_to' for cmd in ops.commands), "Arcs incorrectly generated"

def test_arc_with_trailing_straight_lines():
    ops = Ops()
    radius = 5.0
    center = 0, 0
    
    # Single segment containing:
    # 1. Semicircle (10 points)
    # 2. Straight line (5 points)
    ops.move_to(radius, 0)  # Start at (5,0)
    
    # Semicircle points
    angles = np.linspace(0, np.pi, 10)
    for theta in angles[1:]:  # Skip first point (5,0)
        x = center[0] + radius * np.cos(theta)
        y = center[1] + radius * np.sin(theta)
        ops.line_to(x, y)
    
    # Straight line points
    for x in np.linspace(-5, -10, 5):
        ops.line_to(x, 0)
    
    welder = ArcWeld(tolerance=0.1, min_points=5)
    welder.run(ops)
    
    # Validate results
    commands = ops.commands
    cmd_types = [cmd.name for cmd in commands]
    assert cmd_types == [
        'move_to',
        'arc_to', 
        'line_to',
        'line_to',
        'line_to',
        'line_to',
    ], f"Unexpected command sequence: {cmd_types}"
    
    # Validate arc parameters
    arc_cmd = commands[1]
    end_x, end_y, I, J, clockwise = arc_cmd.args
    assert np.isclose(end_x, -5.0, atol=0.1), "Arc ends at wrong X"
    assert np.isclose(end_y, 0.0, atol=0.1), "Arc ends at wrong Y"
    
    # Validate straight lines after arc
    assert commands[2].args == (-6.25, 0.0)
    assert commands[3].args == (-7.5, 0.0)
    assert commands[4].args == (-8.75, 0.0)
    assert commands[5].args == (-10.0, 0.0)

def test_find_longest_valid_arc():
    welder = ArcWeld(tolerance=0.1)

    # Valid arc segment
    theta = np.linspace(0, np.pi/2, 10)
    arc_points = [(5*np.cos(t), 5*np.sin(t)) for t in theta]
    arc, end = welder._find_longest_valid_arc(arc_points, 0)
    assert arc is not None
    assert end == 10

    # Straight line segment
    line_points = [(x, 0) for x in range(10)]
    arc, end = welder._find_longest_valid_arc(line_points, 0)
    assert arc is None

def test_is_valid_arc():
    welder = ArcWeld(tolerance=0.1)

    # Test 1: Valid arc
    valid_arc = (10.0, 10.0), 50.0, 0.05
    subsegment = [
        (10.0 + 50.0 * np.cos(np.deg2rad(0)), 10.0 + 50.0 * np.sin(np.deg2rad(0))),
        (10.0 + 50.0 * np.cos(np.deg2rad(30)), 10.0 + 50.0 * np.sin(np.deg2rad(30))),
        (10.0 + 50.0 * np.cos(np.deg2rad(60)), 10.0 + 50.0 * np.sin(np.deg2rad(60)))
    ]
    assert welder._is_valid_arc(subsegment, valid_arc) is True

    # Test 2: Error exceeds tolerance
    high_error_arc = *valid_arc[:2], 0.2
    assert welder._is_valid_arc(subsegment, high_error_arc) is False

    # Test 3: Radius too small
    small_radius_arc = valid_arc[0], 0.5, valid_arc[2]
    assert welder._is_valid_arc(subsegment, small_radius_arc) is False

    # Test 4: Radius too large
    large_radius_arc = valid_arc[0], 20000.0, valid_arc[2]
    assert welder._is_valid_arc(subsegment, large_radius_arc) is False

    # Test 5: Colinear points
    colinear_subsegment = [(0.0, 0.0), (2.0, 0.0), (4.0, 0.0)]
    colinear_arc = fit_circle(colinear_subsegment)
    assert welder._is_valid_arc(colinear_subsegment, colinear_arc) is False

    # Test 6: Invalid arc (None)
    assert welder._is_valid_arc(subsegment, None) is False

def test_is_valid_arc_angular_continuity():
    welder = ArcWeld(tolerance=0.1)
    
    # Exact points on a circle (radius 5, center (0,0))
    angles = np.deg2rad([0, 30, 60, 90])
    valid_points = [
        (5 * np.cos(theta), 5 * np.sin(theta)) for theta in angles
    ]
    valid_arc = fit_circle(valid_points)
    assert welder._is_valid_arc(valid_points, valid_arc) is True
    
    # Add point diametrically opposite to start (180° total span)
    invalid_points = valid_points + [(5 * np.cos(np.pi), 5 * np.sin(np.pi))]
    invalid_arc = fit_circle(invalid_points)
    assert welder._is_valid_arc(invalid_points, invalid_arc) is False, \
        "Should reject arc due to large angular step"

def test_arc_processing_flow():
    welder = ArcWeld(tolerance=0.1, min_points=3)
    ops = Ops()
    
    # Exact semicircle points on a circle with radius 5, center (0,0)
    angles = np.linspace(0, np.pi, 12)  # 10 points for 180 degrees
    segment = [
        (5 * np.cos(theta), 
        5 * np.sin(theta))
        for theta in angles
    ]
    
    welder.process_segment(segment, ops)
    
    # Validate command sequence
    cmd_names = [cmd.name for cmd in ops.commands]
    assert cmd_names == ['move_to', 'arc_to'], "Should replace entire segment with one arc"
    
    # Validate arc parameters
    arc_cmd = ops.commands[1]
    end_x, end_y, i, j, clockwise = arc_cmd.args
    assert np.isclose(end_x, -5.0, atol=0.1)
    assert np.isclose(end_y, 0.0, atol=0.1)
    assert np.isclose(i, -5.0, atol=0.1)  # Center (0,0) - start (5,0) → I=-5
    assert np.isclose(j, 0.0, atol=0.1)
    assert not clockwise  # CCW for ascending angles

def test_process_segment_structure():
    welder = ArcWeld(tolerance=0.1)
    ops = Ops()

    # Single straight line segment
    segment = [
        (0, 0), (1, 0), (2, 0), (3, 0), (4, 0)
    ]
    welder.process_segment(segment, ops)
    assert [cmd.name for cmd in ops.commands] == [
        'move_to',
        'line_to',
        'line_to',
        'line_to',
        'line_to',
    ]

def test_move_to_handling():
    welder = ArcWeld()
    ops = Ops()

    # Manually build command sequence
    ops.commands = [
        Command('move_to', (0, 0)),
        Command('line_to', (1, 0)),
        Command('move_to', (2, 0)),
        Command('line_to', (3, 0))
    ]

    # Process commands
    welder.run(ops)

    # Verify output
    assert len(ops.commands) == 4
    assert [cmd.name for cmd in ops.commands] == [
        'move_to', 'line_to',
        'move_to', 'line_to'
    ]
