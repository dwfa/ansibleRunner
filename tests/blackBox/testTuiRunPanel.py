##############################################################################
# TUI run panel black-box tests for ansibleRunner.
#
# USAGE:
#   python3 -m pytest tests/blackBox/testTuiRunPanel.py
#
# WORKFLOW:
#   1. Verify Enter from launch opens the run panel.
#   2. Verify run output is written to a project-local log.
#
# Copyright 2026 Douglas WF Acheson (dwfa@dwfa.ca)
# Licensed under Apache License 2.0. See LICENSE.md for details.
#
# Version: 1.0
# Date: July 12, 2026
##############################################################################

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from textual.widgets import Static

from ansibleRunner.defaults import RuntimeDefaults
from ansibleRunner.playbooks.models import PlaybookConfig
from ansibleRunner.playbooks.playbookConfig import savePlaybookConfigs
from ansibleRunner.tui.app import AnsibleRunnerTui
from ansibleRunner.tui.run.screen import RunScreen


def createPlaybook(projectRoot: Path, name: str = "site-pb") -> None:
    """Create a minimal playbook fixture.

    Args:
        projectRoot: Temporary project root.
        name: Playbook stem without suffix.
    """

    playbookDir = projectRoot / "playbooks"
    playbookDir.mkdir(exist_ok=True)
    (playbookDir / f"{name}.yaml").write_text(
        "# Configure DNS services\n---\n",
        encoding="utf-8",
    )


@pytest.mark.asyncio
async def testTuiRunPanelRunsSelectedPlaybook(
    tmp_path: Path,
    monkeypatch: Any,
) -> None:
    """Verify launch Enter opens run screen and executes the playbook."""

    _writeFakeAnsible(tmp_path, monkeypatch, exitCode=0)
    createPlaybook(tmp_path)
    defaults = RuntimeDefaults.forProject(tmp_path)
    savePlaybookConfigs(
        defaults.stateDir / "playbookConfig.json",
        {"site-pb": PlaybookConfig(node="web")},
    )

    async with AnsibleRunnerTui(defaults).run_test() as pilot:
        await pilot.press("enter")
        await pilot.press("enter")
        await pilot.pause(0.5)

        runScreen = pilot.app.query_one("#run-menu", RunScreen)
        runStatus = pilot.app.query_one("#run-status", Static)
        runTitle = pilot.app.query_one("#run-title", Static)

        assert str(runTitle.content) == "site web"
        assert str(runStatus.content) == "Finished: success"
        assert runScreen.result is not None
        assert runScreen.result.returnCode == 0
        assert runScreen.result.logPath is not None
        assert runScreen.result.logPath.is_file()

        logText = runScreen.result.logPath.read_text(encoding="utf-8")
        assert "cwd=" + str(tmp_path) in logText
        assert "nodes=web" in logText


def _writeFakeAnsible(tmp_path: Path, monkeypatch: Any, exitCode: int) -> None:
    """Write a fake ansible-playbook executable into a temporary PATH."""

    binDir = tmp_path / "bin"
    binDir.mkdir()
    executable = binDir / "ansible-playbook"
    executable.write_text(
        "#!/bin/sh\n"
        "echo cwd=$(pwd)\n"
        "for arg in \"$@\"; do\n"
        "  echo $arg\n"
        "done\n"
        f"exit {exitCode}\n",
        encoding="utf-8",
    )
    executable.chmod(0o755)
    monkeypatch.setenv("PATH", f"{binDir}:{tmp_path}")
