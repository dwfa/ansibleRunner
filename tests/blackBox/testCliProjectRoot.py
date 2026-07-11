##############################################################################
# CLI project-root unit tests for ansibleRunner.
#
# USAGE:
#   python3 -m pytest tests/unit/testCliProjectRoot.py
#
# WORKFLOW:
#   1. Verify CLI project-root defaults.
#   2. Verify CLI project-root overrides.
#
# Copyright 2026 Douglas WF Acheson (dwfa@dwfa.ca)
# Licensed under Apache License 2.0. See LICENSE.md for details.
#
# Version: 1.0
# Date: July 05, 2026
##############################################################################

from __future__ import annotations

from pathlib import Path
from typing import Any

from ansibleRunner import cli


def testCliMainUsesCwdByDefault(
    tmp_path: Path,
    monkeypatch: Any,
    capsys: Any,
) -> None:
    """Verify the CLI uses the current working directory by default."""

    monkeypatch.chdir(tmp_path)

    result = cli.main(["--list-defaults"])

    assert result == 0
    output = capsys.readouterr().out
    assert f"projectRoot={tmp_path.resolve()}" in output


def testCliMainAcceptsExplicitProjectRoot(tmp_path: Path, capsys: Any) -> None:
    """Verify the CLI accepts an explicit project-root override."""

    projectRoot = tmp_path / "elsewhere"
    projectRoot.mkdir()

    result = cli.main(["--project-root", str(projectRoot), "--list-defaults"])

    assert result == 0
    output = capsys.readouterr().out
    assert f"projectRoot={projectRoot.resolve()}" in output
