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
from types import SimpleNamespace
from pathlib import Path
from textwrap import dedent
from time import monotonic
from typing import Any

import pytest
from rich.console import Console
from rich.text import Text
from textual.containers import Container, VerticalScroll
from textual.widgets import Input, Static

import ansibleRunner.tui.run.screen as runScreenModule
from ansibleRunner.defaults import RuntimeDefaults
from ansibleRunner.playbooks.models import PlaybookConfig
from ansibleRunner.playbooks.playbookConfig import savePlaybookConfigs
from ansibleRunner.tui.app import AnsibleRunnerTui
from ansibleRunner.tui.launch.screen import LaunchScreen
from ansibleRunner.tui.run.screen import SPINNER_FRAMES, RunScreen


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


def createRunScreen(projectRoot: Path) -> RunScreen:
    """Create a run screen fixture for direct event processing tests."""

    return RunScreen(
        RuntimeDefaults.forProject(projectRoot),
        entry=SimpleNamespace(
            displayName="site",
            path=projectRoot / "playbooks" / "site-pb.yaml",
            title="site-pb.yaml",
        ),
        config=PlaybookConfig(node="web", outputLevel="task"),
        argsDisplay="",
        onBack=lambda: None,
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


async def waitForActivePrompt(pilot: Any, cycles: int = 100) -> None:
    """Wait for the run screen to show an active prompt."""

    for _ in range(cycles):
        runScreen = pilot.app.query_one("#run-menu", RunScreen)
        if runScreen.activePromptMessage is not None:
            return
        await pilot.pause(0.1)
    raise AssertionError("Run did not show an active prompt before test timeout.")


def testTuiRunPanelProcessesCallbackTaskLifecycle(tmp_path: Path) -> None:
    """Verify callback events can drive active task display and completion."""

    createPlaybook(tmp_path)
    runScreen = createRunScreen(tmp_path)

    runScreen._processEventRecord(
        {
            "event": "play_start",
            "play": {"name": "Bootstrap collections"},
        }
    )
    runScreen._processEventRecord(
        {
            "event": "task_start",
            "task": {
                "name": "bootstrapCollections : install azure SDK pip requirements",
                "role": "bootstrapCollections",
            },
        }
    )

    rows = runScreen.progressParser.rows(now=monotonic())

    assert [(row.icon, row.name, row.status) for row in rows] == [
        ("🎭", "Bootstrap collections", "running"),
        ("⚙", "bootstrapCollections", "running"),
        ("🔧", "install azure SDK pip requirements", "running"),
    ]

    runScreen._processEventRecord({"event": "runner_ok", "result": {}})
    runScreen._processEventRecord(
        {
            "event": "task_start",
            "task": {
                "name": "bootstrapCollections : install optional collection",
                "role": "bootstrapCollections",
            },
        }
    )
    runScreen._processEventRecord({"event": "runner_skipped", "result": {}})
    rows = runScreen.progressParser.rows(now=monotonic())

    assert [(row.icon, row.name, row.status) for row in rows] == [
        ("🎭", "Bootstrap collections", "running"),
        ("⚙", "bootstrapCollections", "running"),
        ("🔧", "install azure SDK pip requirements", "succeeded"),
    ]


def testTuiRunPanelRendersNiceDisplayCallbackPayload(tmp_path: Path) -> None:
    """Verify niceDisplay callback results render as framed preformatted output."""

    createPlaybook(tmp_path)
    runScreen = createRunScreen(tmp_path)

    runScreen._processEventRecord(
        {
            "event": "play_start",
            "play": {"name": "List Postgres Flexible Servers"},
        }
    )
    runScreen._processEventRecord(
        {
            "event": "task_start",
            "task": {
                "name": (
                    "listDBServers : niceDisplay: Postgres Flexible Servers "
                    "matching cei-aztest- (1 found)"
                ),
                "role": "listDBServers",
            },
        }
    )
    runScreen._processEventRecord(
        {
            "event": "runner_ok",
            "result": {
                "changed": False,
                "msg": (
                    "NAME  LOCATION\n"
                    "----  --------\n"
                    "db1   East US\n"
                ),
                "task": {
                    "name": (
                        "listDBServers : niceDisplay: Postgres Flexible Servers "
                        "matching cei-aztest- (1 found)"
                    ),
                    "role": "listDBServers",
                },
            },
        }
    )
    runScreen.progressRows = runScreen.progressParser.rows(now=monotonic())
    renderedProgress = _renderRich(runScreen._renderProgress())

    assert "niceDisplay:" not in renderedProgress
    assert "Postgres Flexible Servers matching cei-aztest- (1 found)" in renderedProgress
    assert "NAME  LOCATION" in renderedProgress
    assert "db1   East US" in renderedProgress
    assert "msg:" not in renderedProgress
    assert runScreen._prettyOutputClipboardText() == (
        "Postgres Flexible Servers matching cei-aztest- (1 found)\n"
        "NAME  LOCATION\n"
        "----  --------\n"
        "db1   East US"
    )


def testTuiRunPanelHidesNiceDisplayIncludeWrapper(tmp_path: Path) -> None:
    """Verify top-level niceDisplay includes do not jump ahead of role rows."""

    createPlaybook(tmp_path)
    runScreen = createRunScreen(tmp_path)

    runScreen._processEventRecord(
        {
            "event": "play_start",
            "play": {"name": "Test a few roles"},
        }
    )
    runScreen._processEventRecord(
        {
            "event": "task_start",
            "task": {
                "action": "ansible.builtin.ping",
                "name": "ping : ping",
                "role": "ping",
            },
        }
    )
    runScreen._processEventRecord({"event": "runner_ok", "result": {}})
    runScreen._processEventRecord(
        {
            "event": "task_start",
            "task": {
                "action": "ansible.builtin.include_tasks",
                "name": "show niceDisplay sample",
                "role": None,
            },
        }
    )
    runScreen._processEventRecord({"event": "runner_ok", "result": {}})
    runScreen._processEventRecord(
        {
            "event": "task_start",
            "task": {
                "action": "ansible.builtin.debug",
                "name": "niceDisplay: Sample table output",
                "role": None,
            },
        }
    )
    runScreen._processEventRecord(
        {
            "event": "runner_ok",
            "result": {
                "msg": "NAME  STATUS\n----  ------\ntest  ok",
                "task": {
                    "action": "ansible.builtin.debug",
                    "name": "niceDisplay: Sample table output",
                    "role": None,
                },
            },
        }
    )
    runScreen.progressParser.finalizePlay(monotonic())
    rows = runScreen.progressParser.rows(now=monotonic())

    assert [(row.depth, row.icon, row.name, row.output is not None) for row in rows] == [
        (0, "🎭", "Test a few roles", False),
        (1, "⚙", "ping", False),
        (2, "🔧", "ping", False),
        (1, "", "", True),
    ]


def testTuiRunPanelFormatsNiceDisplayListAndDictPayloads(tmp_path: Path) -> None:
    """Verify supported niceDisplay payload shapes format without noise."""

    createPlaybook(tmp_path)
    runScreen = createRunScreen(tmp_path)

    assert runScreen._prettyPayloadBody(["one", "two"]) == "one\ntwo"
    assert runScreen._prettyPayloadBody({"name": "db1", "region": "East US"}) == (
        "name: db1\nregion: East US"
    )


def testTuiRunPanelCopiesOutputWithNativeClipboardTool(monkeypatch: Any) -> None:
    """Verify pretty output copy uses an available native clipboard command."""

    calls = []

    def fakeWhich(command: str) -> str | None:
        if command == "pbcopy":
            return "/usr/bin/pbcopy"
        return None

    def fakeRun(command: list[str], **kwargs: object) -> None:
        calls.append((command, kwargs["input"]))

    monkeypatch.setattr(runScreenModule.sys, "platform", "darwin")
    monkeypatch.setattr(runScreenModule.shutil, "which", fakeWhich)
    monkeypatch.setattr(runScreenModule.subprocess, "run", fakeRun)

    assert RunScreen._copyTextWithNativeTool("title\nbody")
    assert calls == [(["pbcopy"], "title\nbody")]


def testTuiRunPanelCopyFallsBackWhenNativeClipboardUnavailable(
    monkeypatch: Any,
) -> None:
    """Verify copy gracefully falls back when native clipboard tools are absent."""

    monkeypatch.setattr(runScreenModule.sys, "platform", "linux")
    monkeypatch.setattr(runScreenModule.shutil, "which", lambda command: None)

    assert not RunScreen._copyTextWithNativeTool("title\nbody")


def testTuiRunPanelCompletedHelpShowsPrettyOutputCopyOptions(
    tmp_path: Path,
) -> None:
    """Verify completed run help shows whole-output and selected-copy options."""

    createPlaybook(tmp_path)
    runScreen = createRunScreen(tmp_path)
    runScreen._processEventRecord(
        {
            "event": "play_start",
            "play": {"name": "List servers"},
        }
    )
    runScreen._processEventRecord(
        {
            "event": "task_start",
            "task": {"name": "niceDisplay: Server summary"},
        }
    )
    runScreen._processEventRecord(
        {
            "event": "runner_ok",
            "result": {
                "msg": "NAME\n----\ndb1",
                "task": {"name": "niceDisplay: Server summary"},
            },
        }
    )
    runScreen.progressRows = runScreen.progressParser.rows(now=monotonic())

    assert runScreen._completedHelpText() == (
        "Enter/Space/Esc back  y copy output  Fn-drag select ⌘C copy"
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
        assert str(runHelp.content) == "Enter/Space/Esc back"
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
        assert "native_ansible_log=1" in logText
        assert "cwd=" + str(tmp_path) in logText
        assert "ANSIBLE_LOG_PATH=" + str(runScreen.result.logPath) in logText
        assert "nodes=web" in logText

        assert [(row.icon, row.name, row.status) for row in runScreen.progressRows] == [
            ("🎭", "Test play", "succeeded"),
            ("⚙", "setup", "succeeded"),
        ]

        await pilot.press("enter")

        assert pilot.app.query_one("#launch-menu", LaunchScreen)


@pytest.mark.asyncio
async def testTuiRunPanelAutoScrollsProgressToEnd(
    tmp_path: Path,
    monkeypatch: Any,
) -> None:
    """Verify progress refresh keeps the live scroll view at the newest rows."""

    _writeFakeAnsible(tmp_path, monkeypatch, exitCode=0)
    createPlaybook(tmp_path)
    defaults = RuntimeDefaults.forProject(tmp_path)
    savePlaybookConfigs(
        defaults.stateDir / "playbookConfig.json",
        {"site-pb": PlaybookConfig(node="web")},
    )
    scrollCalls: list[bool] = []

    async with AnsibleRunnerTui(defaults).run_test() as pilot:
        await pilot.press("enter")
        await pilot.press("enter")
        await pilot.pause(0.1)

        runScreen = pilot.app.query_one("#run-menu", RunScreen)
        runProgressScroll = pilot.app.query_one("#run-progress-scroll", VerticalScroll)
        monkeypatch.setattr(
            runProgressScroll,
            "scroll_end",
            lambda animate=False: scrollCalls.append(animate),
        )
        monkeypatch.setattr(runScreen, "_progressScrollAtBottom", lambda: True)
        runScreen.running = True
        runScreen.followProgress = True

        scrollCalls.clear()
        runScreen._refreshProgress()

        assert scrollCalls
        assert all(call is False for call in scrollCalls)


@pytest.mark.asyncio
async def testTuiRunPanelPausesAutoScrollWhenUserLeavesBottom(
    tmp_path: Path,
    monkeypatch: Any,
) -> None:
    """Verify progress refresh does not follow after the user scrolls up."""

    _writeFakeAnsible(tmp_path, monkeypatch, exitCode=0)
    createPlaybook(tmp_path)
    defaults = RuntimeDefaults.forProject(tmp_path)
    savePlaybookConfigs(
        defaults.stateDir / "playbookConfig.json",
        {"site-pb": PlaybookConfig(node="web")},
    )
    scrollCalls: list[bool] = []

    async with AnsibleRunnerTui(defaults).run_test() as pilot:
        await pilot.press("enter")
        await pilot.press("enter")
        await pilot.pause(0.1)

        runScreen = pilot.app.query_one("#run-menu", RunScreen)
        runProgressScroll = pilot.app.query_one("#run-progress-scroll", VerticalScroll)
        monkeypatch.setattr(
            runProgressScroll,
            "scroll_end",
            lambda animate=False: scrollCalls.append(animate),
        )
        monkeypatch.setattr(runScreen, "_progressScrollAtBottom", lambda: False)
        runScreen.running = True
        runScreen.followProgress = True

        runScreen._refreshProgress()

        assert not runScreen.followProgress
        assert scrollCalls == []


@pytest.mark.asyncio
async def testTuiRunPanelMouseScrollHitTestUsesTextualPoint(
    tmp_path: Path,
    monkeypatch: Any,
) -> None:
    """Verify mouse scroll hit testing matches Textual's point API."""

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
        await pilot.pause(0.1)

        runScreen = pilot.app.query_one("#run-menu", RunScreen)
        runProgressScroll = pilot.app.query_one("#run-progress-scroll", VerticalScroll)
        event = SimpleNamespace(
            screen_x=runProgressScroll.region.x,
            screen_y=runProgressScroll.region.y,
        )

        assert runScreen._eventInProgressScroll(event)


@pytest.mark.asyncio
async def testTuiRunPanelResumesAutoScrollWhenUserReturnsToBottom(
    tmp_path: Path,
    monkeypatch: Any,
) -> None:
    """Verify progress refresh resumes following at the bottom."""

    _writeFakeAnsible(tmp_path, monkeypatch, exitCode=0)
    createPlaybook(tmp_path)
    defaults = RuntimeDefaults.forProject(tmp_path)
    savePlaybookConfigs(
        defaults.stateDir / "playbookConfig.json",
        {"site-pb": PlaybookConfig(node="web")},
    )
    scrollCalls: list[bool] = []

    async with AnsibleRunnerTui(defaults).run_test() as pilot:
        await pilot.press("enter")
        await pilot.press("enter")
        await pilot.pause(0.1)

        runScreen = pilot.app.query_one("#run-menu", RunScreen)
        runProgressScroll = pilot.app.query_one("#run-progress-scroll", VerticalScroll)
        monkeypatch.setattr(
            runProgressScroll,
            "scroll_end",
            lambda animate=False: scrollCalls.append(animate),
        )
        monkeypatch.setattr(runScreen, "_progressScrollAtBottom", lambda: True)
        runScreen.running = True
        runScreen.followProgress = False

        runScreen._refreshProgress()

        assert runScreen.followProgress
        assert scrollCalls


@pytest.mark.asyncio
async def testTuiRunPanelDoesNotAutoScrollAfterRunCompletes(
    tmp_path: Path,
    monkeypatch: Any,
) -> None:
    """Verify completed runs remain scrollable without forced follow."""

    _writeFakeAnsible(tmp_path, monkeypatch, exitCode=0)
    createPlaybook(tmp_path)
    defaults = RuntimeDefaults.forProject(tmp_path)
    savePlaybookConfigs(
        defaults.stateDir / "playbookConfig.json",
        {"site-pb": PlaybookConfig(node="web")},
    )
    scrollCalls: list[bool] = []

    async with AnsibleRunnerTui(defaults).run_test() as pilot:
        await pilot.press("enter")
        await pilot.press("enter")
        await waitForRunComplete(pilot)

        runScreen = pilot.app.query_one("#run-menu", RunScreen)
        runProgressScroll = pilot.app.query_one("#run-progress-scroll", VerticalScroll)
        monkeypatch.setattr(
            runProgressScroll,
            "scroll_end",
            lambda animate=False: scrollCalls.append(animate),
        )
        runScreen.followProgress = True

        runScreen._refreshProgress()

        assert not runScreen.running
        assert scrollCalls == []


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
async def testTuiRunPanelEscapeReturnsAfterCompletedRun(
    tmp_path: Path,
    monkeypatch: Any,
) -> None:
    """Verify Escape returns to launch after a completed run."""

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

        await pilot.press("escape")

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


@pytest.mark.asyncio
async def testTuiRunPanelRunsWhenNodeIsUnset(
    tmp_path: Path,
    monkeypatch: Any,
) -> None:
    """Verify an unset node lets the playbook decide its own hosts."""

    _writeFakeAnsible(tmp_path, monkeypatch, exitCode=0)
    createPlaybook(tmp_path)
    defaults = RuntimeDefaults.forProject(tmp_path)
    savePlaybookConfigs(
        defaults.stateDir / "playbookConfig.json",
        {"site-pb": PlaybookConfig(outputLevel="task")},
    )

    async with AnsibleRunnerTui(defaults).run_test() as pilot:
        await pilot.press("enter")
        await pilot.press("enter")
        await waitForRunComplete(pilot)

        runScreen = pilot.app.query_one("#run-menu", RunScreen)
        runStatus = pilot.app.query_one("#run-status", Static)
        runFailure = pilot.app.query_one("#run-failure", Static)

        assert str(runStatus.content).startswith("Finished: success  elapsed=")
        assert not runFailure.display
        assert runScreen.result is not None
        assert runScreen.result.logPath is not None
        logText = runScreen.result.logPath.read_text(encoding="utf-8")
        assert "nodes=" not in logText
        assert "no node" not in logText

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
        await waitForActivePrompt(pilot)

        runScreen = pilot.app.query_one("#run-menu", RunScreen)
        promptPanel = pilot.app.query_one("#run-prompt-panel", Container)
        promptInput = pilot.app.query_one("#run-prompt-input", Input)
        promptMessage = pilot.app.query_one("#run-prompt-message", Static)
        promptHelp = pilot.app.query_one("#run-prompt-help", Static)
        runProgress = pilot.app.query_one("#run-progress", Static)

        assert promptPanel.display
        assert "Enter/Space continue" in str(promptHelp.content)
        assert str(promptMessage.content) == "wait for user input to continue"
        assert runScreen.activePromptMessage == "wait for user input to continue"
        assert runScreen.activePromptMode == "continue"
        assert not promptInput.display

        await pilot.press("enter")
        await pilot.pause(0.5)

        runStatus = pilot.app.query_one("#run-status", Static)
        renderedProgress = _renderRich(runProgress.content)

        assert str(runStatus.content).startswith("Finished: success  elapsed=")
        assert "💬 wait for user input to continue — continued" in renderedProgress
        assert "💬 wait for user input — continued" not in renderedProgress
        assert "🔧 wait for user input" not in renderedProgress
        assert runScreen.activePromptMessage is None


@pytest.mark.asyncio
async def testTuiRunPanelSubmitsTypedPromptInput(
    tmp_path: Path,
    monkeypatch: Any,
) -> None:
    """Verify typed prompt input is submitted to the active process."""

    _writePromptValueFakeAnsible(tmp_path, monkeypatch)
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
        promptPanel = pilot.app.query_one("#run-prompt-panel", Container)
        promptInput = pilot.app.query_one("#run-prompt-input", Input)
        promptMessage = pilot.app.query_one("#run-prompt-message", Static)
        promptHelp = pilot.app.query_one("#run-prompt-help", Static)
        runProgress = pilot.app.query_one("#run-progress", Static)

        assert runScreen.activePromptMessage == "Prompt for DHCP-assigned IP"
        assert runScreen.activePromptMode == "text"
        assert promptPanel.display
        assert str(promptMessage.content) == "Prompt for DHCP-assigned IP"
        assert str(promptHelp.content) == "Enter submit  Esc cancel"
        assert promptInput.display
        assert not promptInput.password

        await pilot.press("d")
        await pilot.press("n")
        await pilot.press("x")
        await pilot.press("backspace")
        await pilot.press("s")
        await pilot.press("space")
        await pilot.press("1")

        renderedPrompt = _renderRich(runProgress.content)

        assert "Input" in renderedPrompt
        assert promptInput.value == "dns 1"
        assert "dns 1" not in renderedPrompt

        await pilot.press("enter")
        await pilot.pause(0.5)

        assert str(pilot.app.query_one("#run-status", Static).content).startswith(
            "Finished: success  elapsed="
        )
        assert runScreen.activePromptMessage is None
        assert not promptPanel.display
        assert not promptInput.display
        assert any("received=dns 1" in line for line in runScreen.outputLines)

        renderedProgress = _renderRich(runProgress.content)
        assert renderedProgress.count("Prompt for DHCP-assigned IP — continued") == 1
        assert "prompt for user input — continued" not in renderedProgress


@pytest.mark.asyncio
async def testTuiRunPanelMarksUnresolvedPromptAsFailed(
    tmp_path: Path,
    monkeypatch: Any,
) -> None:
    """Verify failed prompt setup is not displayed as continued input."""

    _writeUndefinedPromptFakeAnsible(tmp_path, monkeypatch)
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

        assert runScreen.result is not None
        assert runScreen.result.returnCode == 2
        assert runScreen.activePromptMessage is None
        assert "💬 Input" not in renderedProgress
        assert "Prompt for user input — failed" in renderedProgress
        assert "prompt for user input — continued" not in renderedProgress


@pytest.mark.asyncio
async def testTuiRunPanelSpaceContinuesEmptyPrompt(
    tmp_path: Path,
    monkeypatch: Any,
) -> None:
    """Verify Space submits an empty response when no prompt input exists."""

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
        promptPanel = pilot.app.query_one("#run-prompt-panel", Container)
        promptInput = pilot.app.query_one("#run-prompt-input", Input)

        assert runScreen.activePromptMessage == "wait for user input to continue"
        assert runScreen.activePromptMode == "continue"
        assert promptPanel.display
        assert promptInput.value == ""
        assert not promptInput.display

        await pilot.press("space")
        await pilot.pause(0.5)

        assert str(pilot.app.query_one("#run-status", Static).content).startswith(
            "Finished: success  elapsed="
        )
        assert runScreen.activePromptMessage is None
        assert not promptPanel.display
        assert not promptInput.display


@pytest.mark.asyncio
async def testTuiRunPanelDetectsCustomWaitPromptInclude(
    tmp_path: Path,
    monkeypatch: Any,
) -> None:
    """Verify waitForInput includes show prompts with custom wrapper names."""

    _writeCustomWaitIncludeFakeAnsible(tmp_path, monkeypatch)
    createPlaybook(tmp_path)
    defaults = RuntimeDefaults.forProject(tmp_path)
    savePlaybookConfigs(
        defaults.stateDir / "playbookConfig.json",
        {"site-pb": PlaybookConfig(node="web")},
    )

    async with AnsibleRunnerTui(defaults).run_test() as pilot:
        await pilot.press("enter")
        await pilot.press("enter")
        await waitForActivePrompt(pilot)

        runScreen = pilot.app.query_one("#run-menu", RunScreen)
        promptPanel = pilot.app.query_one("#run-prompt-panel", Container)
        promptInput = pilot.app.query_one("#run-prompt-input", Input)
        promptMessage = pilot.app.query_one("#run-prompt-message", Static)

        assert (
            runScreen.activePromptMessage
            == "Attach external device & press Enter to continue ..."
        )
        assert runScreen.activePromptMode == "continue"
        assert promptPanel.display
        assert (
            str(promptMessage.content)
            == "Attach external device & press Enter to continue ..."
        )
        assert not promptInput.display

        await pilot.press("enter")
        await pilot.pause(0.5)

        runProgress = pilot.app.query_one("#run-progress", Static)
        renderedProgress = _renderRich(runProgress.content)

        assert runScreen.activePromptMessage is None
        assert (
            "💬 Attach external device & press Enter to continue ... — continued"
            in renderedProgress
        )
        assert "🔧 wait for user input" not in renderedProgress


@pytest.mark.asyncio
async def testTuiRunPanelUsesNiceWaitTitle(
    tmp_path: Path,
    monkeypatch: Any,
) -> None:
    """Verify niceWait include titles are used for continue prompts."""

    _writeNiceWaitFakeAnsible(tmp_path, monkeypatch)
    createPlaybook(tmp_path)
    defaults = RuntimeDefaults.forProject(tmp_path)
    savePlaybookConfigs(
        defaults.stateDir / "playbookConfig.json",
        {"site-pb": PlaybookConfig(node="web")},
    )

    async with AnsibleRunnerTui(defaults).run_test() as pilot:
        await pilot.press("enter")
        await pilot.press("enter")
        await waitForActivePrompt(pilot)

        runScreen = pilot.app.query_one("#run-menu", RunScreen)
        promptMessage = pilot.app.query_one("#run-prompt-message", Static)
        promptInput = pilot.app.query_one("#run-prompt-input", Input)

        assert runScreen.activePromptMessage == "Attach external device"
        assert runScreen.activePromptMode == "continue"
        assert str(promptMessage.content) == "Attach external device"
        assert not promptInput.display

        await pilot.press("enter")
        await waitForRunComplete(pilot)

        renderedProgress = _renderRich(
            pilot.app.query_one("#run-progress", Static).content
        )
        assert "Attach external device — continued" in renderedProgress


@pytest.mark.asyncio
async def testTuiRunPanelUsesNicePromptTitle(
    tmp_path: Path,
    monkeypatch: Any,
) -> None:
    """Verify nicePrompt include titles are used for text prompts."""

    _writeNicePromptFakeAnsible(tmp_path, monkeypatch)
    createPlaybook(tmp_path)
    defaults = RuntimeDefaults.forProject(tmp_path)
    savePlaybookConfigs(
        defaults.stateDir / "playbookConfig.json",
        {"site-pb": PlaybookConfig(node="web")},
    )

    async with AnsibleRunnerTui(defaults).run_test() as pilot:
        await pilot.press("enter")
        await pilot.press("enter")
        await waitForActivePrompt(pilot)

        runScreen = pilot.app.query_one("#run-menu", RunScreen)
        promptMessage = pilot.app.query_one("#run-prompt-message", Static)
        promptInput = pilot.app.query_one("#run-prompt-input", Input)

        assert runScreen.activePromptMessage == "Enter DHCP address"
        assert runScreen.activePromptMode == "text"
        assert str(promptMessage.content) == "Enter DHCP address"
        assert promptInput.display

        await pilot.press("1")
        await pilot.press("enter")
        await waitForRunComplete(pilot)

        renderedProgress = _renderRich(
            pilot.app.query_one("#run-progress", Static).content
        )
        assert "Enter DHCP address — continued" in renderedProgress


@pytest.mark.asyncio
async def testTuiRunPanelStartsPromptFromCallbackEvent(
    tmp_path: Path,
    monkeypatch: Any,
) -> None:
    """Verify callback prompt events use native log text for display."""

    _writeEventPromptFakeAnsible(tmp_path, monkeypatch)
    createPlaybook(tmp_path)
    defaults = RuntimeDefaults.forProject(tmp_path)
    savePlaybookConfigs(
        defaults.stateDir / "playbookConfig.json",
        {"site-pb": PlaybookConfig(node="web")},
    )

    async with AnsibleRunnerTui(defaults).run_test() as pilot:
        await pilot.press("enter")
        await pilot.press("enter")
        await waitForActivePrompt(pilot)

        runScreen = pilot.app.query_one("#run-menu", RunScreen)
        promptPanel = pilot.app.query_one("#run-prompt-panel", Container)
        promptInput = pilot.app.query_one("#run-prompt-input", Input)
        promptMessage = pilot.app.query_one("#run-prompt-message", Static)

        assert runScreen.activePromptMessage == "callback supplied prompt text"
        assert runScreen.activePromptMode == "continue"
        assert promptPanel.display
        assert str(promptMessage.content) == "callback supplied prompt text"
        assert not promptInput.display

        await pilot.press("enter")
        await waitForRunComplete(pilot)

        runProgress = pilot.app.query_one("#run-progress", Static)
        renderedProgress = _renderRich(runProgress.content)

        assert "callback supplied prompt text — continued" in renderedProgress


@pytest.mark.asyncio
async def testTuiRunPanelStartsProgressTaskFromCallbackEvent(
    tmp_path: Path,
    monkeypatch: Any,
) -> None:
    """Verify callback task events show active work before stdout task output."""

    _writeEventTaskFakeAnsible(tmp_path, monkeypatch)
    createPlaybook(tmp_path)
    defaults = RuntimeDefaults.forProject(tmp_path)
    savePlaybookConfigs(
        defaults.stateDir / "playbookConfig.json",
        {"site-pb": PlaybookConfig(node="web", outputLevel="task")},
    )

    async with AnsibleRunnerTui(defaults).run_test() as pilot:
        await pilot.press("enter")
        await pilot.press("enter")
        await pilot.pause(0.35)

        runScreen = pilot.app.query_one("#run-menu", RunScreen)
        runProgress = pilot.app.query_one("#run-progress", Static)
        renderedProgress = _renderRich(runProgress.content)

        assert "bootstrapCollections: import azure SDK" in renderedProgress
        assert any(
            row.name == "bootstrapCollections: import azure SDK"
            and row.status == "running"
            for row in runScreen.progressRows
        )

        await waitForRunComplete(pilot)


@pytest.mark.asyncio
async def testTuiRunPanelRendersBracketedPromptTextLiterally(
    tmp_path: Path,
    monkeypatch: Any,
) -> None:
    """Verify prompt text with brackets is not parsed as Rich markup."""

    _writeBracketedPromptFakeAnsible(tmp_path, monkeypatch)
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
        promptMessage = pilot.app.query_one("#run-prompt-message", Static)

        assert (
            runScreen.activePromptMessage
            == "WARNING: About to write [/tmp/currentRPiImage.img] to [/dev/sda]. "
            "This will DESTROY all data on the device. Press Enter to continue "
            "or Ctrl+C then 'A' to abort..."
        )
        assert isinstance(promptMessage.content, Text)
        assert promptMessage.content.plain == runScreen.activePromptMessage

        await pilot.press("enter")
        await pilot.pause(0.5)

        assert runScreen.activePromptMessage is None


@pytest.mark.asyncio
async def testTuiRunPanelRendersMultilinePromptText(
    tmp_path: Path,
    monkeypatch: Any,
) -> None:
    """Verify multiline prompt text is preserved in the prompt panel."""

    _writeMultilineWaitFakeAnsible(tmp_path, monkeypatch)
    createPlaybook(tmp_path)
    defaults = RuntimeDefaults.forProject(tmp_path)
    savePlaybookConfigs(
        defaults.stateDir / "playbookConfig.json",
        {"site-pb": PlaybookConfig(node="web")},
    )

    async with AnsibleRunnerTui(defaults).run_test() as pilot:
        await pilot.press("enter")
        await pilot.press("enter")
        await waitForActivePrompt(pilot)

        runScreen = pilot.app.query_one("#run-menu", RunScreen)
        promptMessage = pilot.app.query_one("#run-prompt-message", Static)

        expectedMessage = (
            "WARNING: About to write image to device.\n"
            "Device: /dev/sda\n"
            "Press Enter to continue."
        )
        assert runScreen.activePromptMessage == expectedMessage
        assert isinstance(promptMessage.content, Text)
        assert promptMessage.content.plain == expectedMessage

        await pilot.press("enter")
        await waitForRunComplete(pilot)

        renderedProgress = _renderRich(
            pilot.app.query_one("#run-progress", Static).content
        )
        assert (
            "WARNING: About to write image to device. — continued"
            in renderedProgress
        )
        assert "Device: /dev/sda — continued" not in renderedProgress


@pytest.mark.asyncio
async def testTuiRunPanelShowsSyntheticWriteTaskAfterDestructivePrompt(
    tmp_path: Path,
    monkeypatch: Any,
) -> None:
    """Verify image-write prompts show the following write task while quiet."""

    _writeSlowImageWritePromptFakeAnsible(tmp_path, monkeypatch)
    createPlaybook(tmp_path)
    defaults = RuntimeDefaults.forProject(tmp_path)
    savePlaybookConfigs(
        defaults.stateDir / "playbookConfig.json",
        {"site-pb": PlaybookConfig(node="web", outputLevel="task")},
    )

    async with AnsibleRunnerTui(defaults).run_test() as pilot:
        await pilot.press("enter")
        await pilot.press("enter")
        await pilot.pause(0.3)

        runScreen = pilot.app.query_one("#run-menu", RunScreen)
        assert runScreen.activePromptMessage is not None

        await pilot.press("enter")
        await pilot.pause(0.15)

        runProgress = pilot.app.query_one("#run-progress", Static)
        renderedProgress = _renderRich(runProgress.content)

        assert "Writing image to device" in renderedProgress
        assert any(frame in renderedProgress for frame in SPINNER_FRAMES)
        assert "write image to device" not in renderedProgress

        await waitForRunComplete(pilot)
        renderedProgress = _renderRich(runProgress.content)

        assert "Writing image to device" in renderedProgress
        assert "write image to device" not in renderedProgress
        assert runScreen.result is not None
        assert runScreen.result.returnCode == 0


@pytest.mark.asyncio
async def testTuiRunPanelShowsSyntheticCopyTaskDuringQuietTransfer(
    tmp_path: Path,
    monkeypatch: Any,
) -> None:
    """Verify quiet remote image copy shows the copy task as active."""

    _writeSlowRemoteCopyFakeAnsible(tmp_path, monkeypatch)
    createPlaybook(tmp_path)
    defaults = RuntimeDefaults.forProject(tmp_path)
    savePlaybookConfigs(
        defaults.stateDir / "playbookConfig.json",
        {"site-pb": PlaybookConfig(node="web", outputLevel="task")},
    )

    async with AnsibleRunnerTui(defaults).run_test() as pilot:
        await pilot.press("enter")
        await pilot.press("enter")
        await pilot.pause(0.25)

        runProgress = pilot.app.query_one("#run-progress", Static)
        renderedProgress = _renderRich(runProgress.content)
        runScreen = pilot.app.query_one("#run-menu", RunScreen)

        assert "Set image path (remote)" in renderedProgress
        assert "Copy image to remote host" in renderedProgress
        assert any(
            row.name == "Copy image to remote host" and row.status == "running"
            for row in runScreen.progressRows
        )

        await waitForRunComplete(pilot)
        renderedProgress = _renderRich(runProgress.content)

        assert "Copy image to remote host" in renderedProgress
        assert "✓" in renderedProgress


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
        assert "💬 wait for user input to continue — continued" in renderedProgress
        assert "💬 wait for user input — continued" not in renderedProgress
        assert "🔧 wait for user input" not in renderedProgress
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
        "if [ -n \"$ANSIBLE_LOG_PATH\" ]; then\n"
        "  {\n"
        "    echo native_ansible_log=1\n"
        "    echo cwd=$(pwd)\n"
        "    echo ANSIBLE_LOG_PATH=$ANSIBLE_LOG_PATH\n"
        "    for arg in \"$@\"; do\n"
        "      echo $arg\n"
        "    done\n"
        "  } > \"$ANSIBLE_LOG_PATH\"\n"
        "fi\n"
        "echo cwd=$(pwd)\n"
        "echo ANSIBLE_LOG_PATH=$ANSIBLE_LOG_PATH\n"
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
            print("\\033[0;35mTASK [pause : wait for user input to continue] ********\\033[0m", flush=True)
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
            print("\\033[0;35mTASK [pause : wait for user input to continue] ********\\033[0m", flush=True)
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


def _writeCustomWaitIncludeFakeAnsible(tmp_path: Path, monkeypatch: Any) -> None:
    """Write a fake ansible-playbook with a custom wait include wrapper."""

    binDir = tmp_path / "bin"
    binDir.mkdir()
    executable = binDir / "ansible-playbook"
    executable.write_text(
        "#!/usr/bin/env python3\n"
        + dedent(
            """
            import os
            import sys

            print("PLAY [Create RPi Image] ********", flush=True)
            print("\\033[0;35mTASK [getInstallDevice : Ask and wait for new device to be attached] ********\\033[0m", flush=True)
            print("included: /tmp/tasks/misc/waitForInput.yaml for 192.168.128.16", flush=True)
            log_path = os.environ.get("ANSIBLE_LOG_PATH")
            if log_path:
                with open(log_path, "a", encoding="utf-8") as log:
                    print("2026-08-01 20:12:52,139 p=1 u=test n=ansible INFO| [getInstallDevice : wait for user input]", file=log)
                    print("Attach external device & press Enter to continue ... (output is hidden):", file=log, flush=True)
            print("[getInstallDevice : wait for user input]", flush=True)
            sys.stdin.readline()
            print("\\033[0;35mTASK [getInstallDevice : Get current block devices] ********\\033[0m", flush=True)
            print("ok: [192.168.128.16]", flush=True)
            sys.exit(0)
            """
        ).lstrip(),
        encoding="utf-8",
    )
    executable.chmod(0o755)
    monkeypatch.setenv("PATH", f"{binDir}:{tmp_path}:{os.environ.get('PATH', '')}")


def _writeNiceWaitFakeAnsible(tmp_path: Path, monkeypatch: Any) -> None:
    """Write a fake ansible-playbook with a niceWait prompt wrapper."""

    binDir = tmp_path / "bin"
    binDir.mkdir()
    executable = binDir / "ansible-playbook"
    executable.write_text(
        "#!/usr/bin/env python3\n"
        + dedent(
            """
            import sys

            print("PLAY [Prompt play] ********", flush=True)
            print("\\033[0;35mTASK [pause : niceWait: Attach external device] ********\\033[0m", flush=True)
            print("included: tasks/misc/waitForInput.yaml for localhost", flush=True)
            print("\\033[0;35mTASK [pause : wait for user input] ********\\033[0m", flush=True)
            sys.stdin.readline()
            print("ok: [localhost]", flush=True)
            sys.exit(0)
            """
        ).lstrip(),
        encoding="utf-8",
    )
    executable.chmod(0o755)
    monkeypatch.setenv("PATH", f"{binDir}:{tmp_path}:{os.environ.get('PATH', '')}")


def _writeNicePromptFakeAnsible(tmp_path: Path, monkeypatch: Any) -> None:
    """Write a fake ansible-playbook with a nicePrompt prompt wrapper."""

    binDir = tmp_path / "bin"
    binDir.mkdir()
    executable = binDir / "ansible-playbook"
    executable.write_text(
        "#!/usr/bin/env python3\n"
        + dedent(
            """
            import sys

            print("PLAY [Prompt play] ********", flush=True)
            print("\\033[0;35mTASK [promptForInput : nicePrompt: Enter DHCP address] ********\\033[0m", flush=True)
            print("included: tasks/misc/promptForInput.yaml for localhost", flush=True)
            print("\\033[0;35mTASK [promptForInput : prompt for user input] ********\\033[0m", flush=True)
            sys.stdin.readline()
            print("ok: [localhost]", flush=True)
            sys.exit(0)
            """
        ).lstrip(),
        encoding="utf-8",
    )
    executable.chmod(0o755)
    monkeypatch.setenv("PATH", f"{binDir}:{tmp_path}:{os.environ.get('PATH', '')}")


def _writeBracketedPromptFakeAnsible(tmp_path: Path, monkeypatch: Any) -> None:
    """Write a fake ansible-playbook with bracketed prompt text."""

    binDir = tmp_path / "bin"
    binDir.mkdir()
    executable = binDir / "ansible-playbook"
    executable.write_text(
        "#!/usr/bin/env python3\n"
        + dedent(
            """
            import os
            import sys

            prompt = (
                "WARNING: About to write [/tmp/currentRPiImage.img] to [/dev/sda]. "
                "This will DESTROY all data on the device. Press Enter to continue "
                "or Ctrl+C then 'A' to abort..."
            )
            print("PLAY [Create RPi Image] ********", flush=True)
            print("\\033[0;35mTASK [createRPiImage : confirm write operation] ********\\033[0m", flush=True)
            print("included: /tmp/tasks/misc/waitForInput.yaml for 192.168.128.16", flush=True)
            log_path = os.environ.get("ANSIBLE_LOG_PATH")
            if log_path:
                with open(log_path, "a", encoding="utf-8") as log:
                    print("2026-08-01 20:20:24,015 p=1 u=test n=ansible INFO| [createRPiImage : wait for user input]", file=log)
                    print(f"{prompt} (output is hidden):", file=log, flush=True)
            print("[createRPiImage : wait for user input]", flush=True)
            sys.stdin.readline()
            print("\\033[0;35mTASK [createRPiImage : write image] ********\\033[0m", flush=True)
            print("ok: [192.168.128.16]", flush=True)
            sys.exit(0)
            """
        ).lstrip(),
        encoding="utf-8",
    )
    executable.chmod(0o755)
    monkeypatch.setenv("PATH", f"{binDir}:{tmp_path}:{os.environ.get('PATH', '')}")


def _writeMultilineWaitFakeAnsible(tmp_path: Path, monkeypatch: Any) -> None:
    """Write a fake ansible-playbook with a multiline native wait prompt."""

    binDir = tmp_path / "bin"
    binDir.mkdir()
    executable = binDir / "ansible-playbook"
    executable.write_text(
        "#!/usr/bin/env python3\n"
        + dedent(
            """
            import os
            import sys

            print("PLAY [Create RPi Image] ********", flush=True)
            print("\\033[0;35mTASK [createRPiImage : niceWait: Confirm write] ********\\033[0m", flush=True)
            print("included: /tmp/tasks/misc/waitForInput.yaml for 192.168.128.16", flush=True)
            log_path = os.environ.get("ANSIBLE_LOG_PATH")
            if log_path:
                with open(log_path, "a", encoding="utf-8") as log:
                    print("2026-08-05 20:20:24,015 p=1 u=test n=ansible INFO| [createRPiImage : wait for user input]", file=log)
                    print("WARNING: About to write image to device.", file=log)
                    print("Device: /dev/sda", file=log)
                    print("Press Enter to continue. (output is hidden):", file=log, flush=True)
                    print("2026-08-05 20:20:25,015 p=1 u=test n=ansible INFO| next log record", file=log, flush=True)
            print("[createRPiImage : wait for user input]", flush=True)
            sys.stdin.readline()
            print("\\033[0;35mTASK [createRPiImage : write image] ********\\033[0m", flush=True)
            print("ok: [192.168.128.16]", flush=True)
            sys.exit(0)
            """
        ).lstrip(),
        encoding="utf-8",
    )
    executable.chmod(0o755)
    monkeypatch.setenv("PATH", f"{binDir}:{tmp_path}:{os.environ.get('PATH', '')}")


def _writeEventPromptFakeAnsible(tmp_path: Path, monkeypatch: Any) -> None:
    """Write a fake ansible-playbook whose prompt is only in callback events."""

    binDir = tmp_path / "bin"
    binDir.mkdir()
    executable = binDir / "ansible-playbook"
    executable.write_text(
        "#!/usr/bin/env python3\n"
        + dedent(
            """
            import json
            import os
            import sys

            log_path = os.environ.get("ANSIBLE_LOG_PATH")
            if log_path:
                with open(log_path, "a", encoding="utf-8") as log:
                    print("2026-08-02 17:00:00,000 p=1 u=test n=ansible INFO| [pause : wait for user input]", file=log)
                    print("callback supplied prompt text (output is hidden):", file=log, flush=True)
            event_log_path = os.environ.get("ANSIBLE_RUNNER_EVENT_LOG")
            if event_log_path:
                with open(event_log_path, "a", encoding="utf-8") as event_log:
                    print(
                        json.dumps(
                            {
                                "event": "task_start",
                                "task": {
                                    "action": "ansible.builtin.pause",
                                    "name": "pause : wait for user input",
                                    "path": "/tmp/tasks/misc/waitForInput.yaml:36",
                                    "role": "pause",
                                    "uuid": None,
                                },
                                "timestamp": "2026-08-02T21:00:00+00:00",
                            },
                            sort_keys=True,
                        ),
                        file=event_log,
                        flush=True,
                    )
            print("PLAY [Callback prompt play] ********", flush=True)
            sys.stdin.readline()
            print("ok: [localhost]", flush=True)
            sys.exit(0)
            """
        ).lstrip(),
        encoding="utf-8",
    )
    executable.chmod(0o755)
    monkeypatch.setenv("PATH", f"{binDir}:{tmp_path}:{os.environ.get('PATH', '')}")


def _writeEventTaskFakeAnsible(tmp_path: Path, monkeypatch: Any) -> None:
    """Write a fake ansible-playbook whose task starts in callback events first."""

    binDir = tmp_path / "bin"
    binDir.mkdir()
    executable = binDir / "ansible-playbook"
    executable.write_text(
        "#!/usr/bin/env python3\n"
        + dedent(
            """
            import json
            import os
            import sys
            import time

            print("PLAY [Bootstrap collections] ********", flush=True)
            event_log_path = os.environ.get("ANSIBLE_RUNNER_EVENT_LOG")
            if event_log_path:
                with open(event_log_path, "a", encoding="utf-8") as event_log:
                    print(
                        json.dumps(
                            {
                                "event": "task_start",
                                "task": {
                                    "action": "ansible.builtin.command",
                                    "name": "bootstrapCollections: import azure SDK",
                                    "path": "/tmp/tasks/bootstrapCollections.yaml:10",
                                    "role": "bootstrapCollections",
                                    "uuid": None,
                                },
                                "timestamp": "2026-08-04T19:41:46+00:00",
                            },
                            sort_keys=True,
                        ),
                        file=event_log,
                        flush=True,
                    )
            time.sleep(0.6)
            print(
                "TASK [bootstrapCollections : bootstrapCollections: import azure SDK] ********",
                flush=True,
            )
            print("ok: [localhost]", flush=True)
            sys.exit(0)
            """
        ).lstrip(),
        encoding="utf-8",
    )
    executable.chmod(0o755)
    monkeypatch.setenv("PATH", f"{binDir}:{tmp_path}:{os.environ.get('PATH', '')}")


def _writeSlowImageWritePromptFakeAnsible(
    tmp_path: Path,
    monkeypatch: Any,
) -> None:
    """Write a fake ansible-playbook with a quiet image write after a prompt."""

    binDir = tmp_path / "bin"
    binDir.mkdir()
    executable = binDir / "ansible-playbook"
    executable.write_text(
        "#!/usr/bin/env python3\n"
        + dedent(
            """
            import os
            import sys
            import time

            prompt = (
                "WARNING: About to write [/tmp/currentRPiImage.img] to [/dev/sda]. "
                "This will DESTROY all data on the device. Press Enter to continue "
                "or Ctrl+C then 'A' to abort..."
            )
            print("PLAY [Create RPi Image] ********", flush=True)
            print("\\033[0;35mTASK [createRPiImage : confirm write operation] ********\\033[0m", flush=True)
            print("included: /tmp/tasks/misc/waitForInput.yaml for 192.168.128.16", flush=True)
            log_path = os.environ.get("ANSIBLE_LOG_PATH")
            if log_path:
                with open(log_path, "a", encoding="utf-8") as log:
                    print("2026-08-01 21:20:24,015 p=1 u=test n=ansible INFO| [createRPiImage : wait for user input]", file=log)
                    print(f"{prompt} (output is hidden):", file=log, flush=True)
            print("[createRPiImage : wait for user input]", flush=True)
            sys.stdin.readline()
            print("\\033[0;35mTASK [createRPiImage : wait for user input] ********\\033[0m", flush=True)
            print("ok: [192.168.128.16]", flush=True)
            time.sleep(0.4)
            print("\\033[0;35mTASK [createRPiImage : write image to device] ********\\033[0m", flush=True)
            print("changed: [192.168.128.16]", flush=True)
            sys.exit(0)
            """
        ).lstrip(),
        encoding="utf-8",
    )
    executable.chmod(0o755)
    monkeypatch.setenv("PATH", f"{binDir}:{tmp_path}:{os.environ.get('PATH', '')}")


def _writeSlowRemoteCopyFakeAnsible(tmp_path: Path, monkeypatch: Any) -> None:
    """Write a fake ansible-playbook with quiet remote copy output."""

    binDir = tmp_path / "bin"
    binDir.mkdir()
    executable = binDir / "ansible-playbook"
    executable.write_text(
        "#!/usr/bin/env python3\n"
        + dedent(
            """
            import sys
            import time

            print("PLAY [Create RPi Image] ********", flush=True)
            print("\\033[0;35mTASK [createRPiImage : Set image path (remote)] ********\\033[0m", flush=True)
            print("ok: [192.168.128.16]", flush=True)
            time.sleep(0.4)
            print("\\033[0;35mTASK [createRPiImage : Copy image to remote host] ********\\033[0m", flush=True)
            print("changed: [192.168.128.16]", flush=True)
            sys.exit(0)
            """
        ).lstrip(),
        encoding="utf-8",
    )
    executable.chmod(0o755)
    monkeypatch.setenv("PATH", f"{binDir}:{tmp_path}:{os.environ.get('PATH', '')}")


def _writePromptValueFakeAnsible(tmp_path: Path, monkeypatch: Any) -> None:
    """Write a fake ansible-playbook that reads prompt input."""

    binDir = tmp_path / "bin"
    binDir.mkdir()
    executable = binDir / "ansible-playbook"
    executable.write_text(
        "#!/usr/bin/env python3\n"
        + dedent(
            """
            import sys

            print("PLAY [Prompt play] ********", flush=True)
            print("\\033[0;35mTASK [promptForInput : Prompt for DHCP-assigned IP] ********\\033[0m", flush=True)
            print("included: tasks/misc/promptForInput.yaml for localhost", flush=True)
            print("\\033[0;35mTASK [promptForInput : prompt for user input] ********\\033[0m", flush=True)
            print("Host [installer] not reachable on port 22.", flush=True)
            print("Enter the DHCP-assigned IP for this host", flush=True)
            value = sys.stdin.readline().rstrip("\\n")
            print("\\033[0;35mTASK [Validate prompted IP format] ********\\033[0m", flush=True)
            print(f"received={value}", flush=True)
            sys.exit(0)
            """
        ).lstrip(),
        encoding="utf-8",
    )
    executable.chmod(0o755)
    monkeypatch.setenv("PATH", f"{binDir}:{tmp_path}:{os.environ.get('PATH', '')}")


def _writeUndefinedPromptFakeAnsible(tmp_path: Path, monkeypatch: Any) -> None:
    """Write a fake ansible-playbook that fails before prompt input."""

    binDir = tmp_path / "bin"
    binDir.mkdir()
    executable = binDir / "ansible-playbook"
    executable.write_text(
        "#!/usr/bin/env python3\n"
        + dedent(
            """
            import sys

            print("PLAY [Prompt play] ********", flush=True)
            print("\\033[0;35mTASK [promptForInput : Prompt for user input] ********\\033[0m", flush=True)
            print("included: tasks/misc/promptForInput.yaml for localhost", flush=True)
            print("\\033[0;35mTASK [promptForInput : prompt for user input] ********\\033[0m", flush=True)
            print("[ERROR]: Task failed: Error while resolving value for 'prompt': 'promptMsg' is undefined", flush=True)
            print("fatal: [localhost]: FAILED! => {\\\"changed\\\": false}", flush=True)
            sys.exit(2)
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
