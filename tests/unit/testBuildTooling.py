##############################################################################
# Build tooling unit tests for ansibleRunner.
#
# USAGE:
#   python3 -m pytest tests/unit/testBuildTooling.py
#
# WORKFLOW:
#   1. Verify build tooling self-bootstraps pytest.
#   2. Verify build.py delegates pytest summary parsing to scripts/test.py.
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


def testToolRequirementsIncludePytest() -> None:
    """Verify the self-bootstrapped toolchain includes pytest."""

    build = _loadBuildModule()

    assert "pytest>=8" in build.TOOL_REQUIREMENTS


def testSummarizePytestOutputDelegatesToTestScript() -> None:
    """Verify build.py can surface pytest summaries from scripts/test.py."""

    build = _loadBuildModule()
    output = (
        "============================= test session starts ==============================\n"
        "collected 23 items\n"
        "============================== 23 passed in 0.29s ==============================\n"
    )
    assert build.summarizePytestOutput(output) == "23 passed in 0.29s"


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
