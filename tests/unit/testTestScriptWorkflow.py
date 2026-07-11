##############################################################################
# Test script workflow unit tests for ansibleRunner.
#
# USAGE:
#   python3 -m pytest tests/unit/testTestScriptWorkflow.py
#
# WORKFLOW:
#   1. Verify pytest output summaries can be surfaced by scripts/test.py.
#   2. Verify the callable test runner builds the expected pytest command.
#
# Copyright 2026 Douglas WF Acheson (dwfa@dwfa.ca)
# Licensed under Apache License 2.0. See LICENSE.md for details.
#
# Version: 1.0
# Date: July 06, 2026
##############################################################################

from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path
from typing import Any


def testSummarizePytestOutputFindsFinalSummary() -> None:
    """Verify pytest output summaries can be surfaced in script output."""

    testScript = _loadTestScriptModule()
    output = (
        "============================= test session starts ==============================\n"
        "collected 23 items\n"
        "============================== 23 passed in 0.29s ==============================\n"
    )

    assert testScript.summarizePytestOutput(output) == "23 passed in 0.29s"


def testSummarizePytestOutputReturnsEmptyWhenMissing() -> None:
    """Verify missing pytest summaries are ignored gracefully."""

    testScript = _loadTestScriptModule()

    assert testScript.summarizePytestOutput("no summary here") == ""


def testRunTestSuiteUsesResolvedTargets(monkeypatch: Any, tmp_path: Path) -> None:
    """Verify runTestSuite builds a pytest command for resolved targets."""

    testScript = _loadTestScriptModule()
    calls: list[tuple[list[str], Path | str | None]] = []

    def fakeRunCommand(
        command: list[str],
        cwd: Path | str | None = None,
        logger: Any = None,
    ) -> subprocess.CompletedProcess[str]:
        """Capture pytest command execution."""

        del logger
        calls.append((command, cwd))
        return subprocess.CompletedProcess(
            command,
            0,
            stdout="============================== 1 passed in 0.01s ==============================\n",
            stderr="",
        )

    testsDir = tmp_path / "tests" / "unit"
    testsDir.mkdir(parents=True)
    monkeypatch.setattr(testScript, "runCommand", fakeRunCommand)

    result = testScript.runTestSuite(
        tmp_path,
        "python",
        ["unit"],
        emitOutput=False,
    )

    assert result.returnCode == 0
    assert result.summary == "1 passed in 0.01s"
    assert calls == [(["python", "-m", "pytest", "tests/unit"], tmp_path)]


def _loadTestScriptModule() -> Any:
    """Load scripts/test.py as an importable test module."""

    scriptPath = Path(__file__).resolve().parents[2] / "scripts" / "test.py"
    spec = importlib.util.spec_from_file_location("ansibleRunnerTestScript", scriptPath)
    assert spec is not None
    assert spec.loader is not None

    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module
