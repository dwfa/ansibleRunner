##############################################################################
# CLI entry point unit tests for ansibleRunner.
#
# USAGE:
#   python3 -m pytest tests/unit/testCliEntryPoint.py
#
# WORKFLOW:
#   1. Verify the configured console entry point is importable.
#
# Copyright 2026 Douglas WF Acheson (dwfa@dwfa.ca)
# Licensed under Apache License 2.0. See LICENSE.md for details.
#
# Version: 1.0
# Date: July 05, 2026
##############################################################################

from __future__ import annotations


def testConsoleScriptEntryPointResolves() -> None:
    """Verify the configured console entry point imports."""

    from ansibleRunner.cli import main as cliMain

    assert callable(cliMain)
