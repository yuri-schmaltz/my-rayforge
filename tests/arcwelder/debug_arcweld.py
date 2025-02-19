import matplotlib.pyplot as plt
import numpy as np
from rayforge.models.ops import Ops
from rayforge.opstransformer.arcwelder import ArcWeld

def debug_arc_fitting():
    # Create test shape: ┌┐ with semicircle top
    ops = Ops()
    
    # Left vertical line
    ops.move_to(0, 0)
    ops.line_to(0, 5)
    
    # Semicircle (should become one arc_to)
    angles = np.linspace(np.pi/2, -np.pi/2, 20)
    for theta in angles:
        x = 5 + 5 * np.cos(theta)
        y = 5 + 5 * np.sin(theta)
        ops.line_to(x, y)
    
    # Right vertical line
    ops.line_to(10, 5)
    ops.line_to(10, 0)

    # Process with arcwelder
    original_commands = ops.commands.copy()
    welder = ArcWeld(tolerance=0.1, min_points=5)
    welder.run(ops)
    processed_commands = ops.commands

    # Plot visualization
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 6))
    
    # Plot original
    original_points = [cmd.args for cmd in original_commands if cmd.name in ('move_to', 'line_to')]
    x_orig, y_orig = zip(*original_points)
    ax1.plot(x_orig, y_orig, 'b.-', label='Original')
    ax1.set_title('Original Path')
    ax1.axis('equal')

    # Plot processed
    x_proc, y_proc = [], []
    current_pos = None
    for cmd in processed_commands:
        if cmd.name == 'move_to':
            current_pos = cmd.args
            x_proc.append(current_pos[0])
            y_proc.append(current_pos[1])
        elif cmd.name == 'line_to':
            x_proc.append(cmd.args[0])
            y_proc.append(cmd.args[1])
            current_pos = cmd.args
        elif cmd.name == 'arc_to':
            # Approximate arc with 50 points
            end_x, end_y, I, J, clockwise = cmd.args
            center = (current_pos[0] + I, current_pos[1] + J)
            radius = np.hypot(I, J)
            
            start_angle = np.arctan2(current_pos[1] - center[1], 
                                   current_pos[0] - center[0])
            end_angle = np.arctan2(end_y - center[1],
                                 end_x - center[0])
            
            angles = np.linspace(start_angle, end_angle, 50)
            if clockwise:
                angles = angles[::-1]
                
            arc_points = [
                (center[0] + radius * np.cos(theta),
                 center[1] + radius * np.sin(theta))
                for theta in angles
            ]
            x_proc.extend([p[0] for p in arc_points])
            y_proc.extend([p[1] for p in arc_points])
            current_pos = (end_x, end_y)

    ax2.plot(x_proc, y_proc, 'r.-', label='Processed')
    ax2.set_title('ArcWelder Processed')
    ax2.axis('equal')

    plt.show()
    
    # Print command sequence for inspection
    print("\nOriginal commands:")
    for cmd in original_commands:
        print(f"{cmd.name}: {cmd.args}")
        
    print("\nProcessed commands:")
    for cmd in processed_commands:
        print(f"{cmd.name}: {cmd.args}")

debug_arc_fitting()
