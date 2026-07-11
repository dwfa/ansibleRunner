##############################################################################
# Standalone shim execution end-to-end tests for ansibleRunner.
#
# USAGE:
#   python3 -m pytest tests/endToEnd/testShimExecution.py
#
# WORKFLOW:
#   1. Verify the shim runs installed ansibleRunner under project .venv.
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


def testMainRunsInstalledToolkitFromCurrentDirectory(
    tmp_path: Path,
    monkeypatch: Any,
) -> None:
    """Verify main uses cwd as project root and runs installed ansibleRunner."""

    shim = _loadShimModule()
    calls: list[list[str]] = []
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(shim, "ensureVenv", lambda venvDir: None)
    monkeypatch.setattr(shim, "ensurePackageInstalled", lambda pythonBin: None)
    monkeypatch.setattr(
        shim.subprocess,
        "run",
        lambda command, check=False: calls.append(command)
        or subprocess.CompletedProcess(command, 0),
    )

    result = shim.main(["--list-defaults"])

    assert result == 0
    assert calls == [
        [
            str(tmp_path / ".venv" / "bin" / "python"),
            "-m",
            "ansibleRunner",
            "--project-root",
            str(tmp_path),
            "--list-defaults",
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
