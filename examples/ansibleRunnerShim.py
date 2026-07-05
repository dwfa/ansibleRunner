#!/usr/bin/env python3
##############################################################################
# Standalone ansibleRunner project shim.
#
# USAGE:
#   cd /path/to/ansible/project
#   ./ansibleRunnerShim.py --list-defaults
#
# WORKFLOW:
#   1. Treat the current working directory as the Ansible project root.
#   2. Create .venv under the project root when needed.
#   3. Install ansibleRunner from the local test wheel when missing.
#   4. Run the installed ansibleRunner toolkit under the project .venv.
#
# OUTPUT VARIABLES:
#   - .venv: Project-local Python virtual environment.
#
# Copyright 2026 Douglas WF Acheson (dwfa@dwfa.ca)
# Licensed under Apache License 2.0. See LICENSE.md for details.
#
# Version: 1.0
# Date: July 05, 2026
##############################################################################

"""Standalone project shim for testing ansibleRunner from a built wheel."""

from __future__ import annotations

import os
import subprocess
import sys
import venv
from pathlib import Path


PACKAGE_NAME = "ansibleRunner"
WHEEL_PATH = Path(
    "/Volumes/dwfaData/Projects/ansible/ansibleRunner/dist/"
    "ansiblerunner-0.1.0-py3-none-any.whl"
)


def main(argv: list[str] | None = None) -> int:
    """Run the installed ansibleRunner toolkit through a project-local venv.

    Args:
        argv: Optional arguments excluding the executable name.

    Returns:
        Process exit code from the installed ansibleRunner module.
    """

    args = list(sys.argv[1:] if argv is None else argv)
    projectRoot = Path.cwd().resolve()
    venvDir = projectRoot / ".venv"
    venvPython = getVenvPython(venvDir)

    ensureVenv(venvDir)
    ensurePackageInstalled(venvPython)

    command = [
        str(venvPython),
        "-m",
        PACKAGE_NAME,
        "--project-root",
        str(projectRoot),
        *args,
    ]
    return subprocess.run(command, check=False).returncode


def ensurePackageInstalled(pythonBin: Path) -> None:
    """Install ansibleRunner from the test wheel when missing.

    Args:
        pythonBin: Project virtual environment Python executable.
    """

    if isPackageInstalled(pythonBin):
        return
    if not WHEEL_PATH.is_file():
        raise SystemExit(f"ansibleRunner wheel not found: {WHEEL_PATH}")

    print(f"Installing {PACKAGE_NAME} from {WHEEL_PATH}", file=sys.stderr)
    result = subprocess.run(
        [
            str(pythonBin),
            "-m",
            "pip",
            "install",
            "--upgrade",
            str(WHEEL_PATH),
        ],
        check=False,
        text=True,
    )
    if result.returncode != 0:
        raise SystemExit(result.returncode)


def ensureVenv(venvDir: Path) -> None:
    """Create the project-local virtual environment when missing.

    Args:
        venvDir: Project-local virtual environment directory.
    """

    if venvDir.exists():
        return
    print(f"Creating project venv: {venvDir}", file=sys.stderr)
    venv.create(venvDir, with_pip=True)


def getVenvPython(venvDir: Path) -> Path:
    """Return the Python executable path for a virtual environment.

    Args:
        venvDir: Virtual environment directory.

    Returns:
        Path to the virtual environment Python executable.
    """

    if os.name == "nt":
        return venvDir / "Scripts" / "python.exe"
    return venvDir / "bin" / "python"


def isPackageInstalled(pythonBin: Path) -> bool:
    """Check whether ansibleRunner is importable in the venv.

    Args:
        pythonBin: Python executable to inspect.

    Returns:
        True when ansibleRunner is importable, otherwise False.
    """

    result = subprocess.run(
        [
            str(pythonBin),
            "-c",
            (
                "import importlib.util, sys; "
                f"sys.exit(0 if importlib.util.find_spec({PACKAGE_NAME!r}) else 1)"
            ),
        ],
        check=False,
    )
    return result.returncode == 0


if __name__ == "__main__":
    raise SystemExit(main())
