##############################################################################
# Runtime default unit tests for ansibleRunner.
#
# USAGE:
#   python3 -m pytest tests/unit/testRuntimeDefaults.py
#
# WORKFLOW:
#   1. Verify RuntimeDefaults resolves arPath values.
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


def testRuntimeDefaultsForArPathAcceptsPath(tmp_path: Path) -> None:
    """Verify RuntimeDefaults accepts Path arPath values."""

    defaults = RuntimeDefaults.forArPath(tmp_path)

    assert defaults.arPath == tmp_path.resolve()
    assert defaults.pbPath == tmp_path.resolve() / "playbooks"


def testRuntimeDefaultsForArPathAcceptsString(tmp_path: Path) -> None:
    """Verify RuntimeDefaults accepts string arPath values."""

    defaults = RuntimeDefaults.forArPath(str(tmp_path))

    assert defaults.arPath == tmp_path.resolve()


def testRuntimeDefaultsAreArPathLocal(tmp_path: Path) -> None:
    """Verify log and state paths stay under arPath."""

    defaults = RuntimeDefaults.forArPath(tmp_path)

    assert defaults.logDir == tmp_path.resolve() / "logs"
    assert defaults.stateDir == tmp_path.resolve() / ".ansibleRunner" / "state"


def testRuntimeDefaultsAcceptsExplicitPlaybookPath(tmp_path: Path) -> None:
    """Verify playbook discovery can be anchored outside arPath."""

    arPath = tmp_path / "runner"
    pbPath = tmp_path / "ansible" / "playbooks"

    defaults = RuntimeDefaults.forArPath(arPath, pbPath)

    assert defaults.arPath == arPath.resolve()
    assert defaults.pbPath == pbPath.resolve()
    assert defaults.logDir == arPath.resolve() / "logs"
    assert defaults.stateDir == arPath.resolve() / ".ansibleRunner" / "state"


def testRuntimeDefaultsDoesNotCreateDirectories(tmp_path: Path) -> None:
    """Verify resolving defaults has no filesystem side effects."""

    defaults = RuntimeDefaults.forArPath(tmp_path)

    assert not defaults.logDir.exists()
    assert not defaults.stateDir.exists()
    assert not (tmp_path / ".ansibleRunner").exists()
    assert not (tmp_path / "logs").exists()
