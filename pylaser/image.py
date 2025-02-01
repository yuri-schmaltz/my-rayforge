def convert_surface_to_greyscale(surface):
    """Converts a cairo surface to greyscale."""
    data = surface.get_data()
    for i in range(0, len(data), 4):
        r = data[i]
        g = data[i + 1]
        b = data[i + 2]
        grey = int(0.299 * r + 0.587 * g + 0.114 * b)
        data[i] = grey
        data[i + 1] = grey
        data[i + 2] = grey
    return surface  # Return the modified surface
