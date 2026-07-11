##############################################################################
# Standalone shim bootstrap end-to-end tests for ansibleRunner.
#
# USAGE:
#   python3 -m pytest tests/endToEnd/testShimBootstrap.py
#
# WORKFLOW:
#   1. Verify venv path helpers.
#   2. Verify package-install checks.
#
# Copyright 2026 Douglas WF Acheson (dwfa@dwfa.ca)
# Licensed under Apache License 2.0. See LICENSE.md for details.
#
# Version: 1.0
# Date: July 05, 2026
##############################################################################

from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path
from typing import Any


def testGetVenvPythonUsesProjectVenvBin() -> None:
    """Verify POSIX venv Python path resolution."""

    shim = _loadShimModule()

    assert shim.getVenvPython(Path("/project/.venv")) == Path(
        "/project/.venv/bin/python"
    )


def testEnsureVenvCreatesMissingVenv(tmp_path: Path, monkeypatch: Any) -> None:
    """Verify missing project venvs are created."""

    shim = _loadShimModule()
    calls: list[Path] = []
    monkeypatch.setattr(
        shim.venv,
        "create",
        lambda venvDir, with_pip: calls.append(venvDir),
    )

    shim.ensureVenv(tmp_path / ".venv")

    assert calls == [tmp_path / ".venv"]


def testEnsureVenvLeavesExistingVenv(tmp_path: Path, monkeypatch: Any) -> None:
    """Verify existing project venvs are reused."""

    shim = _loadShimModule()
    venvDir = tmp_path / ".venv"
    venvDir.mkdir()
    calls: list[Path] = []
    monkeypatch.setattr(
        shim.venv,
        "create",
        lambda venvDir, with_pip: calls.append(venvDir),
    )

    shim.ensureVenv(venvDir)

    assert calls == []


def testIsPackageInstalledUsesVenvPython(monkeypatch: Any) -> None:
    """Verify package checks run through the project venv Python."""

    shim = _loadShimModule()
    calls: list[list[str]] = []

    def fakeRun(command: list[str], check: bool = False) -> Any:
        """Capture package-check command."""

        calls.append(command)
        return subprocess.CompletedProcess(command, 0)

    monkeypatch.setattr(shim.subprocess, "run", fakeRun)

    assert shim.isPackageInstalled(Path("/project/.venv/bin/python")) is True
    assert calls[0][0] == "/project/.venv/bin/python"
    assert calls[0][1] == "-c"


def testEnsurePackageInstalledSkipsInstalledPackage(monkeypatch: Any) -> None:
    """Verify install is skipped when ansibleRunner is already importable."""

    shim = _loadShimModule()
    calls: list[list[str]] = []
    monkeypatch.setattr(shim, "isPackageInstalled", lambda pythonBin: True)
    monkeypatch.setattr(
        shim.subprocess,
        "run",
        lambda command, **kwargs: calls.append(command),
    )

    shim.ensurePackageInstalled(Path("/project/.venv/bin/python"))

    assert calls == []


def testEnsurePackageInstalledInstallsWheel(monkeypatch: Any, tmp_path: Path) -> None:
    """Verify missing ansibleRunner installs from the configured wheel."""

    shim = _loadShimModule()
    wheelPath = tmp_path / "ansiblerunner-0.1.0-py3-none-any.whl"
    wheelPath.write_text("wheel\n", encoding="utf-8")
    calls: list[list[str]] = []
    monkeypatch.setattr(shim, "WHEEL_PATH", wheelPath)
    monkeypatch.setattr(shim, "isPackageInstalled", lambda pythonBin: False)
    monkeypatch.setattr(
        shim.subprocess,
        "run",
        lambda command, **kwargs: calls.append(command)
        or subprocess.CompletedProcess(command, 0),
    )

    shim.ensurePackageInstalled(Path("/project/.venv/bin/python"))

    assert calls == [
        [
            "/project/.venv/bin/python",
            "-m",
            "pip",
            "install",
            "--upgrade",
            str(wheelPath),
        ]
    ]


def _loadShimModule() -> Any:
    """Load the standalone shim as an importable test module."""

    shimPath = Path(__file__).resolve().parent / "ansibleRunnerShim.py"
    spec = importlib.util.spec_from_file_location("ansibleRunnerShim", shimPath)
    assert spec is not None
    assert spec.loader is not None

    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module
