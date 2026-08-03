#!/usr/bin/env python3
##############################################################################
# GitHub bootstrap installer for ansibleRunner.
#
# USAGE:
#   curl -O https://raw.githubusercontent.com/dwfa/ansibleRunner/v1.0.0/install.py
#   python3 install.py
#
# WORKFLOW:
#   1. Treat the current working directory as the Ansible project root.
#   2. Create .venv under the project root when needed.
#   3. Install ansibleRunner from GitHub into the project .venv.
#   4. Write a thin project-local launcher.
#
# Copyright 2026 Douglas WF Acheson (dwfa@dwfa.ca)
# Licensed under Apache License 2.0. See LICENSE.md for details.
#
# Version: 1.0
# Date: August 03, 2026
##############################################################################

"""Install ansibleRunner from GitHub into a project-local virtual environment."""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path


PACKAGE_NAME = "ansibleRunner"
DEFAULT_REPO_URL = "https://github.com/dwfa/ansibleRunner.git"
DEFAULT_REF = "v1.0.0"
DEFAULT_LAUNCHER_NAME = "ansibleRunner.py"


def main(argv: list[str] | None = None) -> int:
    """Install ansibleRunner and write a project-local launcher.

    Args:
        argv: Optional arguments excluding the executable name.

    Returns:
        Process exit code.
    """

    args = parseArgs(argv)
    projectRoot = args.projectRoot.expanduser().resolve()
    venvDir = args.venvDir.expanduser()
    if not venvDir.is_absolute():
        venvDir = projectRoot / venvDir
    packageSpec = getPackageSpec(args)
    launcherPath = projectRoot / args.launcherName
    venvPython = getVenvPython(venvDir)

    ensureVenv(venvDir, args.python)
    installPackage(venvPython, packageSpec)
    writeLauncher(launcherPath, venvDir)

    print(f"Installed {PACKAGE_NAME} into {venvDir}")
    print(f"Launcher: {launcherPath}")
    print(f"Run: {launcherPath}")
    return 0


def parseArgs(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse installer arguments.

    Args:
        argv: Optional arguments excluding the executable name.

    Returns:
        Parsed arguments.
    """

    parser = argparse.ArgumentParser(
        description="Install ansibleRunner from GitHub into a project .venv."
    )
    parser.add_argument(
        "--project-root",
        dest="projectRoot",
        type=Path,
        default=Path(os.environ.get("ANSIBLE_RUNNER_PROJECT_ROOT", Path.cwd())),
        help="Ansible project root. Defaults to the current directory.",
    )
    parser.add_argument(
        "--venv-dir",
        dest="venvDir",
        type=Path,
        default=Path(os.environ.get("ANSIBLE_RUNNER_VENV", ".venv")),
        help="Virtual environment path. Relative paths are under project root.",
    )
    parser.add_argument(
        "--python",
        default=os.environ.get("PYTHON", sys.executable),
        help="Python executable used to create the virtual environment.",
    )
    parser.add_argument(
        "--repo-url",
        dest="repoUrl",
        default=os.environ.get("ANSIBLE_RUNNER_REPO_URL", DEFAULT_REPO_URL),
        help="Git repository URL used when --package-spec is not set.",
    )
    parser.add_argument(
        "--ref",
        default=os.environ.get("ANSIBLE_RUNNER_REF", DEFAULT_REF),
        help="Git ref used when --package-spec is not set.",
    )
    parser.add_argument(
        "--package-spec",
        dest="packageSpec",
        default=os.environ.get("ANSIBLE_RUNNER_PACKAGE_SPEC"),
        help="Full pip package spec override, for forks or local testing.",
    )
    parser.add_argument(
        "--launcher-name",
        dest="launcherName",
        default=os.environ.get("ANSIBLE_RUNNER_LAUNCHER", DEFAULT_LAUNCHER_NAME),
        help="Project-local launcher filename to write.",
    )
    return parser.parse_args(argv)


def getPackageSpec(args: argparse.Namespace) -> str:
    """Return the pip package spec for ansibleRunner.

    Args:
        args: Parsed installer arguments.

    Returns:
        PEP 508 direct reference package spec.
    """

    if args.packageSpec:
        return str(args.packageSpec)
    return f"{PACKAGE_NAME} @ git+{args.repoUrl}@{args.ref}"


def ensureVenv(venvDir: Path, pythonBin: str) -> None:
    """Create the project-local virtual environment when missing.

    Args:
        venvDir: Virtual environment directory.
        pythonBin: Python executable used to create the virtual environment.
    """

    if getVenvPython(venvDir).exists():
        return
    print(f"Creating virtual environment: {venvDir}")
    subprocess.run([pythonBin, "-m", "venv", str(venvDir)], check=True)


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


def installPackage(pythonBin: Path, packageSpec: str) -> None:
    """Install ansibleRunner into the virtual environment.

    Args:
        pythonBin: Virtual environment Python executable.
        packageSpec: Pip package spec to install.
    """

    command = [
        str(pythonBin),
        "-m",
        "pip",
        "install",
        "--upgrade",
        packageSpec,
    ]
    print(f"Installing {packageSpec}")
    subprocess.run(command, check=True)


def writeLauncher(launcherPath: Path, venvDir: Path) -> None:
    """Write a thin launcher that runs ansibleRunner from the project .venv.

    Args:
        launcherPath: Launcher file to create.
        venvDir: Virtual environment directory.
    """

    launcherPath.write_text(
        getLauncherText(launcherPath.parent, venvDir),
        encoding="utf-8",
    )
    launcherPath.chmod(0o755)


def getLauncherText(projectRoot: Path, venvDir: Path) -> str:
    """Return project launcher source text.

    Args:
        projectRoot: Project root where the launcher is written.
        venvDir: Virtual environment directory.

    Returns:
        Python launcher source code.
    """

    venvExpression = getLauncherVenvExpression(projectRoot, venvDir)
    return f"""#!/usr/bin/env python3
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent
VENV_DIR = {venvExpression}
if os.name == "nt":
    VENV_PYTHON = VENV_DIR / "Scripts" / "python.exe"
else:
    VENV_PYTHON = VENV_DIR / "bin" / "python"

command = [
    str(VENV_PYTHON),
    "-m",
    "ansibleRunner",
    "--project-root",
    str(PROJECT_ROOT),
    *sys.argv[1:],
]
raise SystemExit(subprocess.run(command, check=False).returncode)
"""


def getLauncherVenvExpression(projectRoot: Path, venvDir: Path) -> str:
    """Return source code for resolving the launcher virtual environment.

    Args:
        projectRoot: Project root where the launcher is written.
        venvDir: Virtual environment directory.

    Returns:
        Python source expression for the launcher.
    """

    try:
        relativeVenv = venvDir.relative_to(projectRoot)
    except ValueError:
        return f"Path({str(venvDir)!r})"
    return f"PROJECT_ROOT / {str(relativeVenv)!r}"


if __name__ == "__main__":
    raise SystemExit(main())
