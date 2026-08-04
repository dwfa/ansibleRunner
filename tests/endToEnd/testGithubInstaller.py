##############################################################################
# GitHub installer end-to-end tests for ansibleRunner.
#
# USAGE:
#   python3 -m pytest tests/endToEnd/testGithubInstaller.py
#
# WORKFLOW:
#   1. Verify installer argument defaults and package spec creation.
#   2. Verify venv, pip install, and launcher commands are project-local.
#
# Copyright 2026 Douglas WF Acheson (dwfa@dwfa.ca)
# Licensed under Apache License 2.0. See LICENSE.md for details.
#
# Version: 1.0
# Date: August 03, 2026
##############################################################################

from __future__ import annotations

import importlib.util
import os
import stat
import subprocess
import sys
from pathlib import Path
from typing import Any


def testPackageSpecDefaultsToV1ReleaseWheel() -> None:
    """Verify the installer defaults to the v1.0.1 release wheel."""

    installer = _loadInstallerModule()
    args = installer.parseArgs([])

    assert installer.getPackageSpec(args) == (
        "ansibleRunner @ https://github.com/dwfa/ansibleRunner/releases/download/"
        "v1.0.1/ansiblerunner-1.0.1-py3-none-any.whl"
    )


def testPackageSpecPrefersProjectLocalWheel(tmp_path: Path) -> None:
    """Verify a manually downloaded release wheel is used when present."""

    installer = _loadInstallerModule()
    wheelPath = tmp_path / "ansiblerunner-1.0.1-py3-none-any.whl"
    wheelPath.write_text("wheel\n", encoding="utf-8")
    args = installer.parseArgs([])

    assert installer.getPackageSpec(args, tmp_path) == str(wheelPath)


def testPackageSpecCanInstallFromGit() -> None:
    """Verify the installer can still install from Git for development."""

    installer = _loadInstallerModule()
    args = installer.parseArgs(["--install-from-git"])

    assert installer.getPackageSpec(args) == (
        "ansibleRunner @ git+https://github.com/dwfa/ansibleRunner.git@v1.0.1"
    )


def testPackageSpecCanBeOverridden() -> None:
    """Verify forks, branches, and local package specs can be supplied."""

    installer = _loadInstallerModule()
    args = installer.parseArgs(["--package-spec", "/tmp/ansibleRunner"])

    assert installer.getPackageSpec(args) == "/tmp/ansibleRunner"


def testEnsureVenvCreatesMissingEnvironment(monkeypatch: Any, tmp_path: Path) -> None:
    """Verify the installer creates a missing project virtual environment."""

    installer = _loadInstallerModule()
    calls: list[list[str]] = []

    def fakeRun(command: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        """Capture subprocess calls."""

        calls.append(command)
        return subprocess.CompletedProcess(command, 0)

    monkeypatch.setattr(installer.subprocess, "run", fakeRun)

    created = installer.ensureVenv(
        tmp_path / ".venv",
        "python3",
        tmp_path / "install.log",
    )

    assert created is True
    assert calls == [["python3", "-m", "venv", str(tmp_path / ".venv")]]


def testEnsureVenvReusesExistingEnvironment(
    monkeypatch: Any, tmp_path: Path
) -> None:
    """Verify existing virtual environments are reused."""

    installer = _loadInstallerModule()
    venvPython = tmp_path / ".venv" / "bin" / "python"
    venvPython.parent.mkdir(parents=True)
    venvPython.write_text("python\n", encoding="utf-8")
    calls: list[list[str]] = []

    monkeypatch.setattr(
        installer.subprocess,
        "run",
        lambda command, **kwargs: calls.append(command),
    )

    created = installer.ensureVenv(
        tmp_path / ".venv",
        "python3",
        tmp_path / "install.log",
    )

    assert created is False
    assert calls == []


def testInstallPackageUsesVenvPip(monkeypatch: Any, tmp_path: Path) -> None:
    """Verify pip installation runs inside the project virtual environment."""

    installer = _loadInstallerModule()
    calls: list[list[str]] = []

    def fakeRun(command: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        """Capture subprocess calls."""

        calls.append(command)
        return subprocess.CompletedProcess(command, 0)

    monkeypatch.setattr(installer.subprocess, "run", fakeRun)

    installer.installPackage(
        Path("/project/.venv/bin/python"),
        "ansibleRunner @ https://github.com/dwfa/ansibleRunner/releases/download/"
        "v1.0.1/ansiblerunner-1.0.1-py3-none-any.whl",
        tmp_path / "logs" / "install.log",
    )

    assert calls == [
        [
            "/project/.venv/bin/python",
            "-m",
            "pip",
            "install",
            "--upgrade",
            "--disable-pip-version-check",
            "ansibleRunner @ https://github.com/dwfa/ansibleRunner/releases/download/"
            "v1.0.1/ansiblerunner-1.0.1-py3-none-any.whl",
        ]
    ]


def testInstallLogPathUsesProjectLogs(tmp_path: Path) -> None:
    """Verify installer logs are written under project logs."""

    installer = _loadInstallerModule()

    logPath = installer.getInstallLogPath(tmp_path)

    assert logPath.parent == tmp_path / "logs"
    assert logPath.name.startswith("ansibleRunner-install-")
    assert logPath.suffix == ".log"


def testWriteLauncherRunsInstalledPackage(tmp_path: Path) -> None:
    """Verify the generated launcher delegates to the installed package."""

    installer = _loadInstallerModule()
    launcherPath = tmp_path / "ar.py"

    installer.writeLauncher(launcherPath, tmp_path / ".venv")

    launcherText = launcherPath.read_text(encoding="utf-8")
    assert "PROJECT_ROOT / '.venv'" in launcherText
    assert 'RUNNER = VENV_DIR / "bin" / "ansibleRunner"' in launcherText
    assert '"--project-root",' in launcherText
    assert os.access(launcherPath, os.X_OK)
    assert launcherPath.stat().st_mode & stat.S_IXUSR


def testInstallerSyntaxIsValid() -> None:
    """Verify install.py is executable Python source."""

    installerPath = Path(__file__).resolve().parents[2] / "install.py"

    result = subprocess.run(
        [sys.executable, "-m", "py_compile", str(installerPath)],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr


def _loadInstallerModule() -> Any:
    """Load install.py as an importable test module."""

    installerPath = Path(__file__).resolve().parents[2] / "install.py"
    spec = importlib.util.spec_from_file_location(
        "ansibleRunnerInstaller",
        installerPath,
    )
    assert spec is not None
    assert spec.loader is not None

    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module
