##############################################################################
# Command-line contract tests for ansibleRunner.
#
# USAGE:
#   python3 -m pytest tests/testCli.py
#
# WORKFLOW:
#   1. Verify CLI project-root defaults and overrides.
#   2. Verify argparse error and help behavior.
#   3. Verify the configured console entry point is importable.
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

import pytest

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


def testCliMainRejectsUnknownFlag(
    tmp_path: Path,
    monkeypatch: Any,
    capsys: Any,
) -> None:
    """Verify unknown CLI flags fail with argparse's standard exit code."""

    monkeypatch.chdir(tmp_path)

    with pytest.raises(SystemExit) as exc:
        cli.main(["--definitely-not-a-real-flag"])

    assert exc.value.code == 2
    capsys.readouterr()


def testCliHelpDoesNotCrash(
    tmp_path: Path,
    monkeypatch: Any,
    capsys: Any,
) -> None:
    """Verify CLI help exits successfully and documents public flags."""

    monkeypatch.chdir(tmp_path)

    with pytest.raises(SystemExit) as exc:
        cli.main(["--help"])

    assert exc.value.code == 0
    output = capsys.readouterr().out
    assert "--list-defaults" in output
    assert "--project-root" in output


def testConsoleScriptEntryPointResolves() -> None:
    """Verify the configured console entry point imports."""

    from ansibleRunner.cli import main as cliMain

    assert callable(cliMain)

