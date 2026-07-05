##############################################################################
# Runtime default unit tests for ansibleRunner.
#
# USAGE:
#   python3 -m pytest tests/testDefaults.py
#
# WORKFLOW:
#   1. Verify RuntimeDefaults resolves project roots.
#   2. Verify log and state defaults remain project-local.
#   3. Verify default resolution has no filesystem side effects.
#
# Copyright 2026 Douglas WF Acheson (dwfa@dwfa.ca)
# Licensed under Apache License 2.0. See LICENSE.md for details.
#
# Version: 1.0
# Date: July 05, 2026
##############################################################################

from pathlib import Path

from ansibleRunner.defaults import RuntimeDefaults


def testRuntimeDefaultsForProjectAcceptsPath(tmp_path: Path) -> None:
    """Verify RuntimeDefaults accepts Path project roots."""

    defaults = RuntimeDefaults.forProject(tmp_path)

    assert defaults.projectRoot == tmp_path.resolve()


def testRuntimeDefaultsForProjectAcceptsString(tmp_path: Path) -> None:
    """Verify RuntimeDefaults accepts string project roots."""

    defaults = RuntimeDefaults.forProject(str(tmp_path))

    assert defaults.projectRoot == tmp_path.resolve()


def testRuntimeDefaultsAreProjectLocal(tmp_path: Path) -> None:
    """Verify log and state paths stay under the project root."""

    defaults = RuntimeDefaults.forProject(tmp_path)

    assert defaults.logDir == tmp_path.resolve() / ".ansibleRunner" / "logs"
    assert defaults.stateDir == tmp_path.resolve() / ".ansibleRunner" / "state"


def testRuntimeDefaultsDoesNotCreateDirectories(tmp_path: Path) -> None:
    """Verify resolving defaults has no filesystem side effects."""

    defaults = RuntimeDefaults.forProject(tmp_path)

    assert not defaults.logDir.exists()
    assert not defaults.stateDir.exists()
    assert not (tmp_path / ".ansibleRunner").exists()
