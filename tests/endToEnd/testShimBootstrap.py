##############################################################################
# Standalone shim bootstrap end-to-end tests for ansibleRunner.
#
# USAGE:
#   python3 -m pytest tests/endToEnd/testShimBootstrap.py
#
# WORKFLOW:
#   1. Verify venv path helpers.
#   2. Verify package installation always refreshes from the wheel.
#
# Copyright 2026 Douglas WF Acheson (dwfa@dwfa.ca)
# Licensed under Apache License 2.0. See LICENSE.md for details.
#
# Version: 1.0
# Date: July 05, 2026
##############################################################################

from __future__ import annotations

import importlib.util
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


def testGetLogPathUsesProjectLogs(tmp_path: Path) -> None:
    """Verify shim logs are project-local."""

    shim = _loadShimModule()

    logPath = shim.getLogPath(tmp_path)

    assert logPath.parent == tmp_path / "logs"
    assert logPath.name.startswith("shim-")
    assert logPath.suffix == ".log"


def testInstallPackageAlwaysInstallsWheel(monkeypatch: Any, tmp_path: Path) -> None:
    """Verify ansibleRunner always installs from the configured wheel."""

    shim = _loadShimModule()
    wheelPath = tmp_path / "ansiblerunner-1.0.2-py3-none-any.whl"
    wheelPath.write_text("wheel\n", encoding="utf-8")
    logPath = tmp_path / "logs" / "shim.log"
    calls: list[list[str]] = []

    def fakeRun(command: list[str], **kwargs: Any) -> Any:
        """Capture package install command and write fake pip output."""

        calls.append(command)
        kwargs["stdout"].write("pip output\n")
        return shim.subprocess.CompletedProcess(command, 0)

    monkeypatch.setattr(shim, "WHEEL_PATH", wheelPath)
    monkeypatch.setattr(shim.subprocess, "run", fakeRun)

    shim.installPackage(Path("/project/.venv/bin/python"), logPath)

    assert calls == [
        [
            "/project/.venv/bin/python",
            "-m",
            "pip",
            "install",
            "--upgrade",
            "--force-reinstall",
            str(wheelPath),
        ]
    ]
    assert "pip output" in logPath.read_text(encoding="utf-8")


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
