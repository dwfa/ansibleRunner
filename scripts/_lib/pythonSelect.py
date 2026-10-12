##############################################################################
# Interpreter selection helpers for scripts/*.py.
#
# USAGE:
#   from _lib.pythonSelect import MIN_PYTHON, reexecIfNeeded
#   reexecIfNeeded(MIN_PYTHON)      # must be called BEFORE any 3.10+-only import
#
# WORKFLOW:
#   1. reexecIfNeeded checks sys.version_info against the requested minimum.
#   2. When too old, it searches PATH and standard Homebrew/system locations
#      for a suitable Python interpreter.
#   3. If one is found, the current process is replaced via os.execv.
#   4. If none is found, SystemExit is raised with a diagnostic message.
#
# NOTES:
#   - Keep this module compatible with Python 3.6+: it is imported by the
#     old interpreter that first launched the script.
#   - This module intentionally has no third-party dependencies.
#
# Copyright 2026 Douglas WF Acheson (dwfa@dwfa.ca)
# Licensed under Apache License 2.0. See LICENSE.md for details.
#
# Version: 1.0
# Date: October 13, 2026
##############################################################################

"""Pick a suitable Python interpreter for scripts/*.py."""

from __future__ import annotations

import logging
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Optional, Tuple


MIN_PYTHON: Tuple[int, int] = (3, 10)

PYTHON_SEARCH_CANDIDATES: Tuple[str, ...] = (
    "python3.14",
    "python3.13",
    "python3.12",
    "python3.11",
    "python3.10",
)
PYTHON_SEARCH_DIRS: Tuple[str, ...] = (
    "/opt/homebrew/bin",
    "/opt/homebrew/opt/python@3.14/bin",
    "/opt/homebrew/opt/python@3.13/bin",
    "/opt/homebrew/opt/python@3.12/bin",
    "/opt/homebrew/opt/python@3.11/bin",
    "/opt/homebrew/opt/python@3.10/bin",
    "/usr/local/bin",
    "/usr/local/opt/python@3.14/bin",
    "/usr/local/opt/python@3.13/bin",
    "/usr/local/opt/python@3.12/bin",
    "/usr/local/opt/python@3.11/bin",
    "/usr/local/opt/python@3.10/bin",
    "/usr/bin",
)


def pythonVersion(
    pythonBin: str,
    logger: Optional[logging.Logger] = None,
) -> Optional[Tuple[int, int]]:
    """Return the (major, minor) version of a Python executable, or None.

    Args:
        pythonBin: Path to a Python executable to probe.
        logger: Optional logger for diagnostic output.

    Returns:
        (major, minor) tuple when the executable reports a version, else None.
    """

    try:
        result = subprocess.run(
            [
                pythonBin,
                "-c",
                "import sys; print(sys.version_info[0], sys.version_info[1])",
            ],
            check=False,
            capture_output=True,
            text=True,
            timeout=10,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        if logger is not None:
            logger.debug(
                "<pythonVersion> probe failed: python=[%s] error=[%s]",
                pythonBin,
                exc,
            )
        return None
    if result.returncode != 0:
        if logger is not None:
            logger.debug(
                "<pythonVersion> non-zero: python=[%s] returnCode=[%s] stderr=[%s]",
                pythonBin,
                result.returncode,
                result.stderr.strip(),
            )
        return None
    try:
        major, minor = result.stdout.strip().split()
        return int(major), int(minor)
    except ValueError:
        if logger is not None:
            logger.debug(
                "<pythonVersion> unparsed: python=[%s] stdout=[%s]",
                pythonBin,
                result.stdout.strip(),
            )
        return None


def findSuitablePython(
    minVersion: Tuple[int, int] = MIN_PYTHON,
    logger: Optional[logging.Logger] = None,
) -> Optional[str]:
    """Search PATH and known interpreter locations for a Python >= minVersion.

    Args:
        minVersion: Minimum (major, minor) version required.
        logger: Optional logger for diagnostic output.

    Returns:
        Absolute path to a suitable Python executable, or None when none found.
    """

    seen: set = set()
    candidates = []
    for name in PYTHON_SEARCH_CANDIDATES:
        found = shutil.which(name)
        if found:
            candidates.append(found)
    for directory in PYTHON_SEARCH_DIRS:
        for name in PYTHON_SEARCH_CANDIDATES:
            candidate = Path(directory) / name
            if candidate.is_file():
                candidates.append(str(candidate))
    for name in ("python3", "python"):
        found = shutil.which(name)
        if found:
            candidates.append(found)

    for candidate in candidates:
        try:
            resolved = str(Path(candidate).resolve())
        except OSError:
            continue
        if resolved in seen:
            continue
        seen.add(resolved)
        version = pythonVersion(resolved, logger)
        if version is None:
            continue
        if logger is not None:
            logger.debug(
                "<findSuitablePython> candidate=[%s] version=[%s.%s]",
                resolved,
                version[0],
                version[1],
            )
        if version >= minVersion:
            return resolved
    return None


def reexecIfNeeded(
    minVersion: Tuple[int, int] = MIN_PYTHON,
    logger: Optional[logging.Logger] = None,
) -> None:
    """Re-execute the current script under a suitable interpreter when needed.

    Call this at the top of a script, before importing modules that need a
    newer Python (e.g. tomllib, PEP 604 unions). When the current interpreter
    already meets minVersion, this returns immediately. Otherwise it searches
    for a usable interpreter and replaces the current process with it,
    preserving sys.argv and the environment.

    An environment flag prevents infinite re-exec loops when the search finds
    only interpreters that still report an old version.

    Args:
        minVersion: Minimum (major, minor) version required.
        logger: Optional logger for diagnostic output.

    Raises:
        SystemExit: When no suitable interpreter is found on this host.
    """

    current = (sys.version_info[0], sys.version_info[1])
    if current >= minVersion:
        return

    guardEnv = "ANSIBLE_RUNNER_PYTHON_SELECT_REEXECED"
    if os.environ.get(guardEnv) == "1":
        raise SystemExit(
            "Python {}.{}+ required, but re-exec selected an interpreter "
            "that still reports {}.{}. Aborting to avoid an exec loop.".format(
                minVersion[0], minVersion[1], current[0], current[1],
            )
        )

    suitable = findSuitablePython(minVersion, logger)
    if suitable is None:
        raise SystemExit(
            "Python {min_major}.{min_minor}+ required to run {script}; "
            "none found on PATH or standard locations. Install one "
            "(e.g. brew install python@3.14) and retry.".format(
                min_major=minVersion[0],
                min_minor=minVersion[1],
                script=Path(sys.argv[0]).name if sys.argv else "this script",
            )
        )

    newEnv = os.environ.copy()
    newEnv[guardEnv] = "1"
    sys.stdout.flush()
    sys.stderr.flush()
    os.execvpe(suitable, [suitable, *sys.argv], newEnv)
