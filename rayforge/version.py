import os
import shutil
import subprocess
import sys
from typing import Optional

__dir__ = os.path.dirname(__file__)


def get_version_from_git() -> Optional[str]:
    # Resolve ``git`` to an absolute path so that the subprocess call
    # uses a fully-qualified executable (avoids partial-path warnings
    # from S607 and is more robust on systems with restricted PATH,
    # e.g. minimal container images).
    git = shutil.which("git")
    if git is None:
        return None

    kwargs = {
        "stderr": subprocess.DEVNULL,
        "cwd": __dir__,
    }
    if sys.platform == "win32":
        kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW

    try:
        # ``git`` is resolved via ``shutil.which`` and the second
        # argument is a hardcoded constant, so there is no
        # untrusted input here. S603 is a false positive.
        # Use **kwargs to pass the arguments
        output = subprocess.check_output(  # noqa: S603
            [git, "describe"], **kwargs
        )
    except (
        subprocess.CalledProcessError,
        FileNotFoundError,
        NotADirectoryError,
    ):
        return None
    return output.decode("ascii").strip()


def get_version_from_pkg() -> Optional[str]:
    try:
        from importlib.metadata import PackageNotFoundError, version
    except ImportError:
        return None

    try:
        return version("rayforge")
    except PackageNotFoundError:
        return None


def get_version_from_file() -> Optional[str]:
    version_file = os.path.join(__dir__, "version.txt")
    try:
        with open(version_file, "r") as f:
            return f.read().strip()
    except FileNotFoundError:
        return None
