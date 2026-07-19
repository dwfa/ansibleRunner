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

import io
import os
from pathlib import Path
from textwrap import dedent
from typing import Any

import pytest
from rich.console import Console
from textual.widgets import Static

from ansibleRunner.defaults import RuntimeDefaults
from ansibleRunner.playbooks.models import PlaybookConfig
from ansibleRunner.playbooks.playbookConfig import savePlaybookConfigs
from ansibleRunner.tui.app import AnsibleRunnerTui
from ansibleRunner.tui.launch.screen import LaunchScreen
from ansibleRunner.tui.run.screen import RunScreen


def _renderRich(renderable: object) -> str:
    """Render a Rich renderable to plain terminal text.

    Args:
        renderable: Rich-compatible renderable.

    Returns:
        Rendered terminal text.
    """

    output = io.StringIO()
    console = Console(color_system=None, file=output, force_terminal=False, width=100)
    console.print(renderable)
    return output.getvalue()


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
        runProgress = pilot.app.query_one("#run-progress", Static)

        assert str(runTitle.content) == "site web"
        assert str(runStatus.content) == "Finished: success"
        renderedProgress = _renderRich(runProgress.content)

        assert "🎭 Test play" in renderedProgress
        assert "   └─ ⚙ setup" in renderedProgress
        progressLines = renderedProgress.splitlines()

        assert "✓    [" in renderedProgress
        assert all(line.index("✓") > 70 for line in progressLines)
        assert runScreen.result is not None
        assert runScreen.result.returnCode == 0
        assert runScreen.result.logPath is not None
        assert runScreen.result.logPath.is_file()

        logText = runScreen.result.logPath.read_text(encoding="utf-8")
        assert "cwd=" + str(tmp_path) in logText
        assert "nodes=web" in logText

        assert [(row.icon, row.name, row.status) for row in runScreen.progressRows] == [
            ("🎭", "Test play", "succeeded"),
            ("⚙", "setup", "succeeded"),
        ]


@pytest.mark.asyncio
async def testTuiRunPanelCanCancelActiveRun(
    tmp_path: Path,
    monkeypatch: Any,
) -> None:
    """Verify c cancels an active run and then allows returning to launch."""

    _writeSlowFakeAnsible(tmp_path, monkeypatch)
    createPlaybook(tmp_path)
    defaults = RuntimeDefaults.forProject(tmp_path)
    savePlaybookConfigs(
        defaults.stateDir / "playbookConfig.json",
        {"site-pb": PlaybookConfig(node="web")},
    )

    async with AnsibleRunnerTui(defaults).run_test() as pilot:
        await pilot.press("enter")
        await pilot.press("enter")
        await pilot.pause(0.2)
        pilot.app.query_one("#run-menu", RunScreen).focus()

        await pilot.press("c")
        await pilot.pause(0.5)

        runScreen = pilot.app.query_one("#run-menu", RunScreen)
        runStatus = pilot.app.query_one("#run-status", Static)

        assert str(runStatus.content) == "Finished: canceled"
        assert runScreen.result is not None
        assert runScreen.result.returnCode == 130

        await pilot.press("escape")

        assert pilot.app.query_one("#launch-menu", LaunchScreen)


@pytest.mark.asyncio
async def testTuiRunPanelEnterSendsInputToActiveRun(
    tmp_path: Path,
    monkeypatch: Any,
) -> None:
    """Verify Enter on the run panel forwards input to the process."""

    _writeInputFakeAnsible(tmp_path, monkeypatch)
    createPlaybook(tmp_path)
    defaults = RuntimeDefaults.forProject(tmp_path)
    savePlaybookConfigs(
        defaults.stateDir / "playbookConfig.json",
        {"site-pb": PlaybookConfig(node="web")},
    )

    async with AnsibleRunnerTui(defaults).run_test() as pilot:
        await pilot.press("enter")
        await pilot.press("enter")
        await pilot.pause(0.2)
        pilot.app.query_one("#run-menu", RunScreen).focus()

        await pilot.press("enter")
        await pilot.pause(0.5)

        runScreen = pilot.app.query_one("#run-menu", RunScreen)
        runStatus = pilot.app.query_one("#run-status", Static)

        assert str(runStatus.content) == "Finished: success"
        assert runScreen.result is not None
        assert runScreen.result.returnCode == 0
        assert any("waiting for input" in line for line in runScreen.outputLines)
        assert any("continued" in line for line in runScreen.outputLines)


@pytest.mark.asyncio
async def testTuiRunPanelEscapeCancelsActiveRunAndStaysInApp(
    tmp_path: Path,
    monkeypatch: Any,
) -> None:
    """Verify Esc cancels an active run without leaving the app."""

    _writeSlowFakeAnsible(tmp_path, monkeypatch)
    createPlaybook(tmp_path)
    defaults = RuntimeDefaults.forProject(tmp_path)
    savePlaybookConfigs(
        defaults.stateDir / "playbookConfig.json",
        {"site-pb": PlaybookConfig(node="web")},
    )

    async with AnsibleRunnerTui(defaults).run_test() as pilot:
        await pilot.press("enter")
        await pilot.press("enter")
        await pilot.pause(0.2)

        pilot.app.query_one("#run-menu", RunScreen).focus()
        await pilot.press("escape")
        await pilot.pause(0.5)

        runScreen = pilot.app.query_one("#run-menu", RunScreen)
        runStatus = pilot.app.query_one("#run-status", Static)

        assert str(runStatus.content) == "Finished: canceled"
        assert runScreen.result is not None
        assert runScreen.result.returnCode == 130


@pytest.mark.asyncio
async def testTuiRunPanelQuitCancelsActiveRunAndStaysInApp(
    tmp_path: Path,
    monkeypatch: Any,
) -> None:
    """Verify q cancels an active run without leaving the app."""

    _writeSlowFakeAnsible(tmp_path, monkeypatch)
    createPlaybook(tmp_path)
    defaults = RuntimeDefaults.forProject(tmp_path)
    savePlaybookConfigs(
        defaults.stateDir / "playbookConfig.json",
        {"site-pb": PlaybookConfig(node="web")},
    )

    async with AnsibleRunnerTui(defaults).run_test() as pilot:
        await pilot.press("enter")
        await pilot.press("enter")
        await pilot.pause(0.2)

        pilot.app.query_one("#run-menu", RunScreen).focus()
        await pilot.press("q")
        await pilot.pause(0.5)

        runScreen = pilot.app.query_one("#run-menu", RunScreen)
        runStatus = pilot.app.query_one("#run-status", Static)

        assert str(runStatus.content) == "Finished: canceled"
        assert runScreen.result is not None
        assert runScreen.result.returnCode == 130


@pytest.mark.asyncio
async def testTuiRunPanelCtrlCExitsProcessCleanly(
    tmp_path: Path,
    monkeypatch: Any,
) -> None:
    """Verify Ctrl-C cancels the active run and exits with code 130."""

    _writeSlowFakeAnsible(tmp_path, monkeypatch)
    createPlaybook(tmp_path)
    defaults = RuntimeDefaults.forProject(tmp_path)
    savePlaybookConfigs(
        defaults.stateDir / "playbookConfig.json",
        {"site-pb": PlaybookConfig(node="web")},
    )
    exitCodes: list[int] = []

    async with AnsibleRunnerTui(defaults).run_test() as pilot:
        monkeypatch.setattr(
            pilot.app,
            "exit",
            lambda result=None, return_code=0, message=None: exitCodes.append(
                return_code
            ),
        )
        await pilot.press("enter")
        await pilot.press("enter")
        await pilot.pause(0.2)

        pilot.app.query_one("#run-menu", RunScreen).focus()
        pilot.app.action_help_quit()
        await pilot.pause(0.5)

        runScreen = pilot.app.query_one("#run-menu", RunScreen)

        assert exitCodes == [130]
        assert runScreen.result is not None
        assert runScreen.result.returnCode == 130


@pytest.mark.asyncio
async def testTuiRunPanelCtrlZSendsSuspendToApp(
    tmp_path: Path,
    monkeypatch: Any,
) -> None:
    """Verify Ctrl-Z delegates to Textual suspend handling."""

    _writeFakeAnsible(tmp_path, monkeypatch, exitCode=0)
    createPlaybook(tmp_path)
    defaults = RuntimeDefaults.forProject(tmp_path)
    savePlaybookConfigs(
        defaults.stateDir / "playbookConfig.json",
        {"site-pb": PlaybookConfig(node="web")},
    )
    suspended: list[bool] = []

    async with AnsibleRunnerTui(defaults).run_test() as pilot:
        monkeypatch.setattr(
            pilot.app,
            "action_suspend_process",
            lambda: suspended.append(True),
        )
        await pilot.press("enter")
        await pilot.press("enter")
        await pilot.pause(0.5)

        pilot.app.query_one("#run-menu", RunScreen).focus()
        await pilot.press("ctrl+z")

        assert suspended == [True]


def _writeFakeAnsible(tmp_path: Path, monkeypatch: Any, exitCode: int) -> None:
    """Write a fake ansible-playbook executable into a temporary PATH."""

    binDir = tmp_path / "bin"
    binDir.mkdir()
    executable = binDir / "ansible-playbook"
    executable.write_text(
        "#!/bin/sh\n"
        "echo cwd=$(pwd)\n"
        "echo 'PLAY [Test play] ********'\n"
        "echo 'TASK [setup : Prepare host] ********'\n"
        "echo 'ok: [localhost]'\n"
        "for arg in \"$@\"; do\n"
        "  echo $arg\n"
        "done\n"
        f"exit {exitCode}\n",
        encoding="utf-8",
    )
    executable.chmod(0o755)
    monkeypatch.setenv("PATH", f"{binDir}:{tmp_path}:{os.environ.get('PATH', '')}")


def _writeInputFakeAnsible(tmp_path: Path, monkeypatch: Any) -> None:
    """Write a fake ansible-playbook executable that waits for input."""

    binDir = tmp_path / "bin"
    binDir.mkdir()
    executable = binDir / "ansible-playbook"
    executable.write_text(
        "#!/usr/bin/env python3\n"
        + dedent(
            """
            import sys

            print("waiting for input", flush=True)
            sys.stdin.readline()
            print("continued", flush=True)
            sys.exit(0)
            """
        ).lstrip(),
        encoding="utf-8",
    )
    executable.chmod(0o755)
    monkeypatch.setenv("PATH", f"{binDir}:{tmp_path}:{os.environ.get('PATH', '')}")


def _writeSlowFakeAnsible(tmp_path: Path, monkeypatch: Any) -> None:
    """Write a fake ansible-playbook executable that waits for cancellation."""

    binDir = tmp_path / "bin"
    binDir.mkdir()
    executable = binDir / "ansible-playbook"
    executable.write_text(
        "#!/usr/bin/env python3\n"
        + dedent(
            """
            import signal
            import sys
            import time

            def stop(signum, frame):
                print("stopped", flush=True)
                sys.exit(130)

            signal.signal(signal.SIGTERM, stop)
            print("started", flush=True)
            while True:
                time.sleep(1)
            """
        ).lstrip(),
        encoding="utf-8",
    )
    executable.chmod(0o755)
    monkeypatch.setenv("PATH", f"{binDir}:{tmp_path}:{os.environ.get('PATH', '')}")
