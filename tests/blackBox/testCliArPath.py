##############################################################################
# CLI arPath unit tests for ansibleRunner.
#
# USAGE:
#   python3 -m pytest tests/blackBox/testCliArPath.py
#
# WORKFLOW:
#   1. Verify CLI arPath defaults.
#   2. Verify CLI arPath overrides.
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

    result = cli.main(["--listDefaults"])

    assert result == 0
    output = capsys.readouterr().out
    assert f"arPath={tmp_path.resolve()}" in output
    assert f"pbPath={tmp_path.resolve() / 'playbooks'}" in output


def testCliMainAcceptsExplicitArPath(tmp_path: Path, capsys: Any) -> None:
    """Verify the CLI accepts an explicit arPath override."""

    arPath = tmp_path / "elsewhere"
    arPath.mkdir()

    result = cli.main(["--arPath", str(arPath), "--listDefaults"])

    assert result == 0
    output = capsys.readouterr().out
    assert f"arPath={arPath.resolve()}" in output


def testCliMainAcceptsExplicitArAndPlaybookPaths(
    tmp_path: Path,
    capsys: Any,
) -> None:
    """Verify CLI path overrides split runtime state from playbooks."""

    arPath = tmp_path / "runner"
    pbPath = tmp_path / "ansible" / "playbooks"
    arPath.mkdir()
    pbPath.mkdir(parents=True)

    result = cli.main(
        [
            "--arPath",
            str(arPath),
            "--pbPath",
            str(pbPath),
            "--listDefaults",
        ]
    )

    assert result == 0
    output = capsys.readouterr().out
    assert f"arPath={arPath.resolve()}" in output
    assert f"pbPath={pbPath.resolve()}" in output
    assert f"logDir={arPath.resolve() / 'logs'}" in output
