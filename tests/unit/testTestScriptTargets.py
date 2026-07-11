##############################################################################
# Test script target unit tests for ansibleRunner.
#
# USAGE:
#   python3 -m pytest tests/unit/testTestScriptTargets.py
#
# WORKFLOW:
#   1. Verify named test scopes resolve to pytest targets.
#   2. Verify path targets can be project-root or tests-relative.
#
# Copyright 2026 Douglas WF Acheson (dwfa@dwfa.ca)
# Licensed under Apache License 2.0. See LICENSE.md for details.
#
# Version: 1.0
# Date: July 06, 2026
##############################################################################

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from typing import Any

import pytest


def testResolveTestTargetsDefaultsToUnit() -> None:
    """Verify omitted targets run the unit scope."""

    testScript = _loadTestScriptModule()
    projectRoot = Path(__file__).resolve().parents[2]

    assert testScript.resolveTestTargets(projectRoot) == ["tests/unit"]


def testSelectedTargetsDefaultsToUnit() -> None:
    """Verify no explicit selection defaults to unit tests."""

    testScript = _loadTestScriptModule()
    args = testScript.parseArgs([])

    assert testScript.selectedTargets(args) == ["unit"]


def testSelectedTargetsCombinesUnitBlackAndWhite() -> None:
    """Verify scope switches are additive."""

    testScript = _loadTestScriptModule()
    args = testScript.parseArgs(["-u", "-b", "-w"])

    assert testScript.selectedTargets(args) == ["unit", "blackBox", "whiteBox"]


def testSelectedTargetsCombinesSwitchesAndPaths() -> None:
    """Verify switches can be combined with explicit path targets."""

    testScript = _loadTestScriptModule()
    args = testScript.parseArgs(["unit/testBuildTooling.py", "-b"])

    assert testScript.selectedTargets(args) == [
        "unit/testBuildTooling.py",
        "blackBox",
    ]


def testResolveTestTargetsAcceptsKnownScopes() -> None:
    """Verify named scopes resolve to test directories."""

    testScript = _loadTestScriptModule()
    projectRoot = Path(__file__).resolve().parents[2]

    assert testScript.resolveTestTargets(projectRoot, ["unit", "all"]) == [
        "tests/unit",
        "tests",
    ]


def testResolveTestTargetsAcceptsProjectRelativePath() -> None:
    """Verify project-relative path targets are accepted."""

    testScript = _loadTestScriptModule()
    projectRoot = Path(__file__).resolve().parents[2]

    assert testScript.resolveTestTargets(
        projectRoot,
        ["tests/unit/testBuildTooling.py"],
    ) == ["tests/unit/testBuildTooling.py"]


def testResolveTestTargetsAcceptsTestsRelativePath() -> None:
    """Verify tests-relative path targets are accepted."""

    testScript = _loadTestScriptModule()
    projectRoot = Path(__file__).resolve().parents[2]

    assert testScript.resolveTestTargets(
        projectRoot,
        ["unit/testBuildTooling.py"],
    ) == ["tests/unit/testBuildTooling.py"]


def testResolveTestTargetsRejectsUnknownTarget() -> None:
    """Verify unknown targets fail before pytest is called."""

    testScript = _loadTestScriptModule()
    projectRoot = Path(__file__).resolve().parents[2]

    with pytest.raises(SystemExit):
        testScript.resolveTestTargets(projectRoot, ["missingScope"])


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
