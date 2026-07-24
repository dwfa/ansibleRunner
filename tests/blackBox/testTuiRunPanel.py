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
import re
from pathlib import Path
from textwrap import dedent
from typing import Any

import pytest
from rich.console import Console
from textual.containers import VerticalScroll
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


async def waitForRunComplete(pilot: Any, cycles: int = 100) -> None:
    """Wait for the run screen worker to finish.

    Args:
        pilot: Textual test pilot.
        cycles: Number of 0.1 second polling cycles.
    """

    for _ in range(cycles):
        runScreen = pilot.app.query_one("#run-menu", RunScreen)
        if runScreen.result is not None:
            return
        await pilot.pause(0.1)
    raise AssertionError("Run did not complete before test timeout.")


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
        await waitForRunComplete(pilot)

        runScreen = pilot.app.query_one("#run-menu", RunScreen)
        runStatus = pilot.app.query_one("#run-status", Static)
        runTitle = pilot.app.query_one("#run-title", Static)
        runFailure = pilot.app.query_one("#run-failure", Static)
        runProgress = pilot.app.query_one("#run-progress", Static)
        runProgressScroll = pilot.app.query_one("#run-progress-scroll", VerticalScroll)
        runHelp = pilot.app.query_one("#run-help", Static)

        assert str(runTitle.content) == "site web"
        assert str(runStatus.content).startswith("Finished: success  elapsed=")
        assert not runFailure.display
        assert str(runHelp.content) == "Enter/Space back"
        assert runProgressScroll.id == "run-progress-scroll"
        renderedProgress = _renderRich(runProgress.content)

        assert "🎭 Test play" in renderedProgress
        assert "   └─ ⚙ setup" in renderedProgress
        progressLines = renderedProgress.splitlines()

        assert "✓" in renderedProgress
        assert any(
            re.search(r"\[\d+(?:\.\d+)?s\]|\[\d+m \d{2}s\]", line)
            for line in progressLines
            if "Test play" in line
        )
        assert any(
            re.search(r"\[\d+(?:\.\d+)?s\]|\[\d+m \d{2}s\]", line)
            for line in progressLines
            if "setup" in line
        )
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

        await pilot.press("enter")

        assert pilot.app.query_one("#launch-menu", LaunchScreen)


@pytest.mark.asyncio
async def testTuiRunPanelSpaceReturnsAfterCompletedRun(
    tmp_path: Path,
    monkeypatch: Any,
) -> None:
    """Verify Space returns to launch after a completed run."""

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
        await waitForRunComplete(pilot)

        assert str(pilot.app.query_one("#run-status", Static).content).startswith(
            "Finished: success  elapsed="
        )

        await pilot.press("space")

        assert pilot.app.query_one("#launch-menu", LaunchScreen)


@pytest.mark.asyncio
async def testTuiRunPanelShowsFailureDetails(
    tmp_path: Path,
    monkeypatch: Any,
) -> None:
    """Verify failed runs show compact failure details and log path."""

    _writeFailingFakeAnsible(tmp_path, monkeypatch)
    createPlaybook(tmp_path)
    defaults = RuntimeDefaults.forProject(tmp_path)
    savePlaybookConfigs(
        defaults.stateDir / "playbookConfig.json",
        {"site-pb": PlaybookConfig(node="web", outputLevel="task")},
    )

    async with AnsibleRunnerTui(defaults).run_test() as pilot:
        await pilot.press("enter")
        await pilot.press("enter")
        await waitForRunComplete(pilot)

        runScreen = pilot.app.query_one("#run-menu", RunScreen)
        runFailure = pilot.app.query_one("#run-failure", Static)
        runProgress = pilot.app.query_one("#run-progress", Static)
        runStatus = pilot.app.query_one("#run-status", Static)
        renderedFailure = _renderRich(runFailure.content)
        renderedProgress = _renderRich(runProgress.content)

        assert not runStatus.display
        assert runFailure.display
        assert "✗ Failure" in renderedFailure
        assert "failedAt" in renderedFailure
        assert "Fail play / setup / Break host" in renderedFailure
        assert "elapsed" in renderedFailure
        assert "log" in renderedFailure
        assert "✗ Failure" not in renderedProgress
        assert "recentOutput:" not in renderedFailure
        assert "simulated failure" not in renderedFailure
        assert runScreen.result is not None
        assert runScreen.result.logPath is not None
        assert f"logs/{runScreen.result.logPath.name}" in renderedFailure
        assert [(row.icon, row.name, row.status) for row in runScreen.progressRows] == [
            ("🎭", "Fail play", "failed"),
            ("⚙", "setup", "failed"),
            ("🔧", "Break host", "failed"),
        ]
        renderedLines = renderedProgress.splitlines()
        assert any(
            re.search(r"\[\d+(?:\.\d+)?s\]|\[\d+m \d{2}s\]", line)
            for line in renderedLines
            if "Fail play" in line
        )
        assert any(
            re.search(r"\[\d+(?:\.\d+)?s\]|\[\d+m \d{2}s\]", line)
            for line in renderedLines
            if "setup" in line
        )
        assert any(
            re.search(r"\[\d+(?:\.\d+)?s\]|\[\d+m \d{2}s\]", line)
            for line in renderedLines
            if "Break host" in line
        )

        await pilot.press("enter")

        assert pilot.app.query_one("#launch-menu", LaunchScreen)


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

        assert str(pilot.app.query_one("#run-status", Static).content).startswith(
            "Running  elapsed="
        )

        await pilot.press("c")
        await pilot.pause(0.5)

        runScreen = pilot.app.query_one("#run-menu", RunScreen)
        runStatus = pilot.app.query_one("#run-status", Static)

        assert str(runStatus.content).startswith("Finished: canceled  elapsed=")
        assert runScreen.result is not None
        assert runScreen.result.returnCode == 130

        await pilot.press("enter")

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

        assert str(runStatus.content).startswith("Finished: success  elapsed=")
        assert runScreen.result is not None
        assert runScreen.result.returnCode == 0
        assert any("waiting for input" in line for line in runScreen.outputLines)
        assert any("continued" in line for line in runScreen.outputLines)


@pytest.mark.asyncio
async def testTuiRunPanelShowsPromptCardAndRecordsInteraction(
    tmp_path: Path,
    monkeypatch: Any,
) -> None:
    """Verify Ansible pause tasks show a prompt and record interaction rows."""

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
        await pilot.pause(0.3)

        runScreen = pilot.app.query_one("#run-menu", RunScreen)
        runProgress = pilot.app.query_one("#run-progress", Static)
        renderedPrompt = _renderRich(runProgress.content)

        assert "💬 Input" in renderedPrompt
        assert "wait of input to continue" in renderedPrompt
        assert runScreen.activePromptMessage == "wait of input to continue"

        await pilot.press("enter")
        await pilot.pause(0.5)

        runStatus = pilot.app.query_one("#run-status", Static)
        renderedProgress = _renderRich(runProgress.content)

        assert str(runStatus.content).startswith("Finished: success  elapsed=")
        assert "💬 wait of input to continue — continued" in renderedProgress
        assert "💬 wait for user input — continued" not in renderedProgress
        assert runScreen.activePromptMessage is None


@pytest.mark.asyncio
async def testTuiRunPanelClearsPromptCardWhenRunFinishes(
    tmp_path: Path,
    monkeypatch: Any,
) -> None:
    """Verify successful completion clears any active prompt card."""

    _writeCompletingPromptFakeAnsible(tmp_path, monkeypatch)
    createPlaybook(tmp_path)
    defaults = RuntimeDefaults.forProject(tmp_path)
    savePlaybookConfigs(
        defaults.stateDir / "playbookConfig.json",
        {"site-pb": PlaybookConfig(node="web")},
    )

    async with AnsibleRunnerTui(defaults).run_test() as pilot:
        await pilot.press("enter")
        await pilot.press("enter")
        await waitForRunComplete(pilot)

        runScreen = pilot.app.query_one("#run-menu", RunScreen)
        runProgress = pilot.app.query_one("#run-progress", Static)
        renderedProgress = _renderRich(runProgress.content)

        assert str(pilot.app.query_one("#run-status", Static).content).startswith(
            "Finished: success  elapsed="
        )
        assert "💬 Input" not in renderedProgress
        assert "💬 wait of input to continue — continued" in renderedProgress
        assert "💬 wait for user input — continued" not in renderedProgress
        assert runScreen.activePromptMessage is None


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

        assert str(runStatus.content).startswith("Finished: canceled  elapsed=")
        assert runScreen.result is not None
        assert runScreen.result.returnCode == 130


@pytest.mark.asyncio
async def testTuiRunPanelQuitDoesNotCancelActiveRun(
    tmp_path: Path,
    monkeypatch: Any,
) -> None:
    """Verify q does not cancel an active run."""

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

        assert not str(runStatus.content).startswith("Finished: canceled")
        assert runScreen.running
        assert runScreen.result is None

        runScreen.action_cancel()
        await pilot.pause(0.5)


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
        await pilot.press("ctrl+c")
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


def _writeFailingFakeAnsible(tmp_path: Path, monkeypatch: Any) -> None:
    """Write a fake ansible-playbook executable that fails."""

    binDir = tmp_path / "bin"
    binDir.mkdir()
    executable = binDir / "ansible-playbook"
    executable.write_text(
        "#!/bin/sh\n"
        "echo 'PLAY [Fail play] ********'\n"
        "echo 'TASK [setup : Break host] ********'\n"
        "echo 'fatal: [localhost]: FAILED! => {\"msg\": \"simulated failure\"}'\n"
        "echo 'PLAY RECAP ********'\n"
        "echo 'localhost : ok=0 changed=0 unreachable=0 failed=1'\n"
        "exit 2\n",
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

            print("PLAY [Prompt play] ********", flush=True)
            print("\\033[0;35mTASK [pause : wait of input to continue] ********\\033[0m", flush=True)
            print("included: tasks/misc/waitForInput.yaml for localhost", flush=True)
            print("[pause : wait for user input]", flush=True)
            print("waiting for input", flush=True)
            sys.stdin.readline()
            print("\\033[0;35mTASK [pause : wait for user input] ********\\033[0m", flush=True)
            print("continued", flush=True)
            sys.exit(0)
            """
        ).lstrip(),
        encoding="utf-8",
    )
    executable.chmod(0o755)
    monkeypatch.setenv("PATH", f"{binDir}:{tmp_path}:{os.environ.get('PATH', '')}")


def _writeCompletingPromptFakeAnsible(tmp_path: Path, monkeypatch: Any) -> None:
    """Write a fake ansible-playbook that completes after a prompt task."""

    binDir = tmp_path / "bin"
    binDir.mkdir()
    executable = binDir / "ansible-playbook"
    executable.write_text(
        "#!/usr/bin/env python3\n"
        + dedent(
            """
            import sys

            print("PLAY [Prompt play] ********", flush=True)
            print("\\033[0;35mTASK [pause : wait of input to continue] ********\\033[0m", flush=True)
            print("included: tasks/misc/waitForInput.yaml for localhost", flush=True)
            print("[pause : wait for user input]", flush=True)
            print("\\033[0;35mTASK [pause : wait for user input] ********\\033[0m", flush=True)
            print("ok: [localhost]", flush=True)
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
