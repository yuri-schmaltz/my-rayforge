"""
Runtime utilities for UI scripts.

This module provides the execution environment for scripts run via
`--uiscript`.
Scripts can explicitly import the app and window instances:

    from rayforge.uiscript import app, win

SECURITY NOTE — `--uiscript` is a deliberate trust boundary
============================================================

The ``--uiscript <file.py>`` command-line option (see ``rayforge/app.py``)
takes a path to a Python script and ``exec()``s it in a background thread
inside the running application process. The script gets full access to
the same Python runtime, the same modules, the same network, and the
same filesystem as the app itself.

This is **equivalent to running ``python -c "..."``** with the user's
own credentials — it is a feature, not a vulnerability. Bandit B102 and
Ruff S102 flag the ``exec()`` call; the ``# noqa: S102`` on line 57
documents the intentional design choice.

**Who is the trust boundary for?**

- **End users running rayforge on their own workstation** are the trust
  authority. They pass a path to a script they (or a trusted source)
  wrote. This is the same trust model as ``python myscript.py`` or
  ``bash ./run.sh``.

- **Multi-tenant environments** (kiosks, shared hosts, CI runners
  accepting untrusted input) are **not** supported. If untrusted users
  can pass ``--uiscript``, they can execute arbitrary code as the user
  running rayforge. Do not invoke rayforge with ``--uiscript`` from a
  context where the script path is user-controlled.

- **CI / headless smoke tests** are fine. The script path is hardcoded
  in the test runner, not derived from untrusted input.

**When reviewing changes to this file, verify:**

1. ``exec()`` is still gated on a user-supplied path passed via
   ``--uiscript`` (not a path derived from an imported file, a
   network response, or any other untrusted source).
2. The script runs in a daemon thread (it cannot block the main
   UI loop indefinitely) and exceptions are caught + logged.
3. The script directory is added to ``sys.path`` only for the
   duration of the script's execution and removed in the ``finally``
   block (no ``sys.path`` poisoning for subsequent runs).
"""

import logging
import sys
import threading
import traceback
from pathlib import Path

logger = logging.getLogger(__name__)

app = None
win = None


def _set_context(application, window):
    """Called by the app to populate the script context."""
    global app, win
    app = application
    win = window


def run_script(script_path: Path, application, window):
    """
    Execute a UI script in a background thread.

    Args:
        script_path: Path to the Python script to execute.
        application: The RayforgeApplication instance.
        window: The MainWindow instance.
    """
    if not script_path.exists():
        logger.error(f"UIScript not found: {script_path}")
        return

    logger.info(f"Executing UI script: {script_path}")

    def execute():
        _set_context(application, window)

        script_globals = {
            "__name__": "__uiscript__",
            "__file__": str(script_path),
        }
        script_dir = str(script_path.parent.resolve())
        sys.path.insert(0, script_dir)
        try:
            with open(script_path, "r") as f:
                code = compile(f.read(), str(script_path), "exec")
            exec(code, script_globals)  # noqa: S102 — --uiscript CLI feature
        except Exception as e:
            logger.error(f"Error executing UI script: {e}")
            traceback.print_exc()
        finally:
            if sys.path[0] == script_dir:
                sys.path.pop(0)

    thread = threading.Thread(target=execute, daemon=True)
    thread.start()
