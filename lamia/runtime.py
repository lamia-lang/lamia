"""Runtime environment utilities — process discovery, executable lookup."""

import os
import shutil
import sys


def find_lamia_bin() -> str:
    """Return the path to the ``lamia`` binary that started this process.

    Since this function is always called from within a running ``lamia``
    process, ``sys.argv[0]`` is the most reliable source — it's the exact
    binary the OS used to invoke us.  We resolve it to an absolute path
    so subprocesses work regardless of cwd changes.

    Falls back to ``shutil.which`` (PATH lookup) only when ``sys.argv[0]``
    doesn't point to an existing file (e.g. ``-m lamia`` invocation via
    ``python -m lamia``).
    """
    argv0 = sys.argv[0]
    resolved = os.path.abspath(argv0)
    if os.path.isfile(resolved):
        return resolved
    found = shutil.which("lamia")
    if found:
        return found
    return f"{sys.executable} -m lamia"
