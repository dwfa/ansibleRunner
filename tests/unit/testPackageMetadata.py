##############################################################################
# Package metadata unit tests for ansibleRunner.
#
# USAGE:
#   python3 -m pytest tests/unit/testPackageMetadata.py
#
# WORKFLOW:
#   1. Verify runtime dependencies needed by installed projects are declared.
#
# Copyright 2026 Douglas WF Acheson (dwfa@dwfa.ca)
# Licensed under Apache License 2.0. See LICENSE.md for details.
#
# Version: 1.0
# Date: August 04, 2026
##############################################################################

from __future__ import annotations

import tomllib
from pathlib import Path


def testRuntimeDependenciesIncludeAnsibleCore() -> None:
    """Verify installed projects receive ansible-playbook in their venv."""

    metadata = _loadPyproject()

    assert "ansible-core>=2.16" in metadata["project"]["dependencies"]


def _loadPyproject() -> dict[str, object]:
    """Load project metadata from pyproject.toml."""

    pyprojectPath = Path(__file__).resolve().parents[2] / "pyproject.toml"
    return tomllib.loads(pyprojectPath.read_text(encoding="utf-8"))
