from .modifier import Modifier


class Optimizer(Modifier):
    """
    Performs path optimization. This is normally not used, because modifiers
    need to be fast enough for rendering and the result SHOULD not alter
    the path, visually.
    But it is a useful aid for debugging the path optimizer.
    """
    def run(self, workstep, surface, pixels_per_mm, ymax):
        workstep.path.optimize()
