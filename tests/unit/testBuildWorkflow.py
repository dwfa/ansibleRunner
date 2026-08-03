##############################################################################
# Build workflow unit tests for ansibleRunner.
#
# USAGE:
#   python3 -m pytest tests/unit/testBuildWorkflow.py
#
# WORKFLOW:
#   1. Verify the build macro runs tests before building the wheel.
#   2. Verify failed tests prevent wheel creation.
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

import pytest


def testMainRunsTestsBeforeWheelBuild(monkeypatch: Any, tmp_path: Path) -> None:
    """Verify the build macro runs tests before building a wheel."""

    build = _loadBuildModule()
    calls: list[str] = []
    wheelPath = tmp_path / "dist" / "ansibleRunner-1.0.0-py3-none-any.whl"
    wheelPath.parent.mkdir()
    wheelPath.write_text("wheel\n", encoding="utf-8")

    monkeypatch.setattr(build, "configureLogging", _fakeConfigureLogging)
    monkeypatch.setattr(build, "requireProjectRoot", lambda context: calls.append("root"))
    monkeypatch.setattr(
        build,
        "ensureBuildPython",
        lambda context, args: calls.append("python") or "python",
    )
    monkeypatch.setattr(
        build,
        "runTests",
        lambda context, pythonBin: calls.append("tests"),
    )
    monkeypatch.setattr(
        build,
        "buildWheel",
        lambda context, pythonBin: calls.append("wheel") or wheelPath,
    )
    monkeypatch.setattr(build, "pruneBuildLogs", lambda context: calls.append("logs"))

    result = build.main(["--out-dir", str(tmp_path / "dist"), "--no-spinner"])

    assert result == 0
    assert calls == ["root", "python", "tests", "wheel", "logs"]


def testMainStopsWhenTestsFail(monkeypatch: Any, tmp_path: Path) -> None:
    """Verify a test failure prevents wheel creation."""

    build = _loadBuildModule()
    calls: list[str] = []

    def failTests(context: Any, pythonBin: str) -> None:
        """Raise the same kind of failure as runTests."""

        calls.append("tests")
        raise SystemExit(5)

    monkeypatch.setattr(build, "configureLogging", _fakeConfigureLogging)
    monkeypatch.setattr(build, "requireProjectRoot", lambda context: calls.append("root"))
    monkeypatch.setattr(
        build,
        "ensureBuildPython",
        lambda context, args: calls.append("python") or "python",
    )
    monkeypatch.setattr(build, "runTests", failTests)
    monkeypatch.setattr(
        build,
        "buildWheel",
        lambda context, pythonBin: calls.append("wheel") or tmp_path / "wheel.whl",
    )

    with pytest.raises(SystemExit) as exc:
        build.main(["--out-dir", str(tmp_path / "dist"), "--no-spinner"])

    assert exc.value.code == 5
    assert calls == ["root", "python", "tests"]


def _fakeConfigureLogging(projectRoot: Path, logFileArg: str | None) -> tuple[Path, Any]:
    """Return a temporary logger for build macro tests."""

    del logFileArg
    import logging

    logger = logging.getLogger("ansibleRunner.testBuild")
    logger.handlers.clear()
    logger.addHandler(logging.NullHandler())
    logger.setLevel(logging.DEBUG)
    return projectRoot / "logs" / "test-build.log", logger


def _loadBuildModule() -> Any:
    """Load scripts/build.py as an importable test module."""

    buildPath = Path(__file__).resolve().parents[2] / "scripts" / "build.py"
    spec = importlib.util.spec_from_file_location("ansibleRunnerBuildScript", buildPath)
    assert spec is not None
    assert spec.loader is not None

    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module
