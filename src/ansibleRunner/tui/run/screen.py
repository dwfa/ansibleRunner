##############################################################################
# Playbook run screen.
#
# USAGE:
#   RunScreen(defaults, entry, config, onBack)
#
# Copyright 2026 Douglas WF Acheson (dwfa@dwfa.ca)
# Licensed under Apache License 2.0. See LICENSE.md for details.
#
# Version: 1.0
# Date: July 12, 2026
##############################################################################

"""Playbook run screen."""

from __future__ import annotations

import re
import json
import shutil
import subprocess
import sys
from collections.abc import Awaitable, Callable
from pathlib import Path
from time import monotonic
from typing import Literal, cast

from rich import box
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from textual import events
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, VerticalScroll
from textual.widgets import Input, Static

from ansibleRunner.defaults import RuntimeDefaults
from ansibleRunner.playbooks.models import PlaybookConfig, PlaybookEntry
from ansibleRunner.playbooks.playbookConfig import buildRunnerArgv
from ansibleRunner.progressParser import (
    ANSI_PATTERN,
    AnsibleProgressParser,
    INCLUDED_PATTERN,
    OutputLevel,
    PrettyOutput,
    ProgressRow,
    RESULT_PATTERN,
)
from ansibleRunner.runner import AnsibleCommandRunner, RunControl, RunnerResult


BackHandler = Callable[[], Awaitable[None]]
PromptMode = Literal["continue", "text"]
RunnerFactory = Callable[[RuntimeDefaults], AnsibleCommandRunner]


TASK_HEADER_PATTERN = re.compile(r"^TASK \[(.+?)\] \*+\s*$")
ANSIBLE_LOG_RECORD_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2} .+? INFO\| (.*)$")
EVENT_LOG_PREFIX = "Event log: "
RUN_LOG_PREFIX = "Logging to "
PROMPT_TITLE_PREFIXES = {
    "niceprompt:": "text",
    "nicewait:": "continue",
}
SPINNER_FRAMES = ("⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏")
STATUS_ICONS = {
    "aborted": "■",
    "failed": "✗",
    "running": "",
    "succeeded": "✓",
}
STATUS_STYLES = {
    "aborted": "yellow",
    "failed": "red",
    "running": "cyan",
    "succeeded": "green",
}


class RunScreen(Container):
    """Run a playbook and display output.

    Args:
        defaults: Resolved project runtime defaults.
        entry: Selected playbook entry.
        config: Launch configuration to execute.
        argsDisplay: Styled argument display text from the launch screen.
        onBack: Callback that returns to launch.
        runnerFactory: Optional runner factory for tests.
    """

    BINDINGS = [
        Binding("ctrl+c", "interrupt_process", "Interrupt", priority=True),
        Binding("ctrl+z", "suspend_process", "Suspend", priority=True),
        Binding("escape", "back", "Back", priority=True),
    ]
    can_focus = True

    def __init__(
        self,
        defaults: RuntimeDefaults,
        entry: PlaybookEntry,
        config: PlaybookConfig,
        argsDisplay: str | Text,
        onBack: BackHandler,
        runnerFactory: RunnerFactory | None = None,
    ) -> None:
        """Initialize the run screen."""

        super().__init__(id="run-menu")
        self.argsDisplay = argsDisplay
        self.config = config
        self.defaults = defaults
        self.entry = entry
        self.followProgress = True
        self.onBack = onBack
        self.progressParser = AnsibleProgressParser(
            cast(OutputLevel, self.config.outputLevel)
        )
        self.progressRows: list[ProgressRow] = []
        self.result: RunnerResult | None = None
        self.runControl = RunControl()
        self.runnerFactory = runnerFactory or self._defaultRunnerFactory
        self.activePromptFromInclude = False
        self.activePromptInput = ""
        self.activePromptMessage: str | None = None
        self.activePromptMode: PromptMode | None = None
        self.activePromptStart: float = 0.0
        self.pendingPromptMessage: str | None = None
        self.pendingPromptMode: PromptMode | None = None
        self.pendingPrettyOutputTitle: str | None = None
        self.pendingSyntheticTaskAfterPrompt: tuple[str, set[str]] | None = None
        self.eventLogOffset = 0
        self.eventLogPath: Path | None = None
        self.runLogPath: Path | None = None
        self.suppressNextPromptResult = False
        self.suppressNextPromptTask = False
        self.runEndTime: float | None = None
        self.runStartTime = 0.0
        self.running = False
        self.spinnerIndex = 0
        self.outputLines: list[str] = []

    def compose(self) -> ComposeResult:
        """Compose the run panel.

        Yields:
            Textual widgets for run output.
        """

        with Container(id="run-panel"):
            with Horizontal(id="run-heading"):
                yield Static("▶ Run", id="run-prefix")
                yield Static(self._playbookNameText(), id="run-title")
                yield Static(self.entry.title, id="run-description")
            with Horizontal(id="run-args"):
                yield Static("Args", id="run-args-label")
                yield Static(self.argsDisplay, id="run-args-value")
            yield Static("Starting ...", id="run-status")
            yield Static("", id="run-failure")
            with VerticalScroll(id="run-progress-scroll"):
                yield Static(
                    Text("Waiting for Ansible progress ...", style="dim"),
                    id="run-progress",
                )
                with Container(id="run-prompt-panel"):
                    yield Static("💬 Input", id="run-prompt-title")
                    yield Static("", id="run-prompt-message")
                    yield Input(
                        compact=True,
                        id="run-prompt-input",
                        placeholder="Input",
                    )
                    yield Static("", id="run-prompt-help")
            yield Static(
                "Enter/Space continue  c/Esc cancel  Ctrl-C exit  Ctrl-Z suspend",
                id="run-help",
            )

    def on_mount(self) -> None:
        """Start the playbook run after mount."""

        self.focus()
        self._hidePromptPanel()
        self.runStartTime = monotonic()
        self.running = True
        self.set_interval(0.2, self._refreshProgress)
        self.run_worker(self._runPlaybook, thread=True)

    async def action_back(self) -> None:
        """Cancel the active run or return after completion."""

        if self.running:
            self.action_cancel()
            return
        await self.onBack()

    async def on_key(self, event: events.Key) -> None:
        """Handle run-screen keys even when a child widget has focus.

        Args:
            event: Key event emitted by Textual.
        """

        if event.key == "ctrl+c":
            event.stop()
            event.prevent_default()
            self.action_interrupt_process()
        elif self.activePromptMessage is not None:
            event.stop()
            event.prevent_default()
            await self._handlePromptKey(event)
        elif event.key in {"enter", "space"}:
            event.stop()
            event.prevent_default()
            await self.action_send_enter()
        elif event.key == "y" and self._hasPrettyOutput():
            event.stop()
            event.prevent_default()
            self.action_copy_pretty_output()
        elif event.key == "c":
            event.stop()
            event.prevent_default()
            self.action_cancel()
        elif event.key == "ctrl+z":
            event.stop()
            event.prevent_default()
            self.action_suspend_process()
        elif event.key == "escape":
            event.stop()
            event.prevent_default()
            await self.action_back()

    def on_mouse_scroll_down(self, event: events.MouseScrollDown) -> None:
        """Resume progress following when the user scrolls back to the bottom."""

        if self._eventInProgressScroll(event):
            self.set_timer(0.0, self._syncProgressFollowFromScroll)

    def on_mouse_scroll_up(self, event: events.MouseScrollUp) -> None:
        """Pause progress following when the user scrolls up in the run log."""

        if self._eventInProgressScroll(event):
            self.followProgress = False

    def action_cancel(self) -> None:
        """Cancel the active run."""

        if not self.running:
            return
        if self.activePromptMessage is not None:
            self._recordPromptInteraction("aborted", aborted=True)
        self.query_one("#run-status", Static).update("Canceling ...")
        self._appendOutput("Cancel requested.")
        self.runControl.cancel()

    def action_interrupt_process(self) -> None:
        """Cancel the active run and exit the TUI process."""

        if self.running:
            self.query_one("#run-status", Static).update("Interrupting ...")
            self._appendOutput("Interrupt requested.")
            self.runControl.cancel()
        self.app.exit(return_code=130)

    def action_copy_pretty_output(self) -> None:
        """Copy visible pretty output blocks to the system clipboard."""

        text = self._prettyOutputClipboardText()
        if not text:
            return
        self.app.copy_to_clipboard(text)
        helpText = self.query_one("#run-help", Static)
        if self._copyTextWithNativeTool(text):
            helpText.update("Copied output to clipboard")
        else:
            helpText.update("Copy sent to terminal clipboard")
        self.set_timer(1.5, lambda: helpText.update(self._completedHelpText()))

    async def action_send_enter(self) -> None:
        """Send input to the active playbook or return after completion."""

        if self.running:
            if self.activePromptMessage is not None:
                self._submitPromptInput()
            else:
                self.runControl.sendInput("\n")
            self._refreshProgress()
            return
        await self.onBack()

    def action_suspend_process(self) -> None:
        """Suspend the TUI process using Textual's app-level handler."""

        self.app.action_suspend_process()

    def on_input_changed(self, event: Input.Changed) -> None:
        """Track prompt input changes without logging the prompt value.

        Args:
            event: Input change event from the prompt input widget.
        """

        if event.input.id != "run-prompt-input":
            return
        self.activePromptInput = event.value
        self._refreshProgress()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        """Submit prompt input when Enter is pressed in the input widget.

        Args:
            event: Input submitted event from the prompt input widget.
        """

        if event.input.id != "run-prompt-input":
            return
        event.stop()
        if self.activePromptMessage is not None:
            self._submitPromptInput()
            self._refreshProgress()

    def _appendOutputFromThread(self, line: str) -> None:
        """Append runner output from a worker thread.

        Args:
            line: Output line from the runner.
        """

        self.app.call_from_thread(self._appendOutput, line)

    def _appendOutput(self, line: str) -> None:
        """Record runner output and refresh parsed progress.

        Args:
            line: Output line from the runner.
        """

        self.outputLines.append(line)
        self._processProgressLine(line)
        self._refreshProgress()

    @staticmethod
    def _defaultRunnerFactory(defaults: RuntimeDefaults) -> AnsibleCommandRunner:
        """Build the default command runner.

        Args:
            defaults: Resolved runtime defaults.

        Returns:
            Command runner rooted in the current project.
        """

        return AnsibleCommandRunner(defaults.projectRoot, defaults.logDir)

    def _finishRun(self, result: RunnerResult) -> None:
        """Render final run status.

        Args:
            result: Completed runner result.
        """

        self.runEndTime = monotonic()
        self.result = result
        self.running = False
        self._finalizeProgress(result)
        status = self.query_one("#run-status", Static)
        helpText = self.query_one("#run-help", Static)
        helpText.update(self._completedHelpText())
        if result.returnCode == 0:
            status.display = True
            status.update(f"Finished: success  elapsed={self._runElapsedText()}")
        elif result.returnCode == 130:
            status.display = True
            status.update(f"Finished: canceled  elapsed={self._runElapsedText()}")
        else:
            status.update("")
            status.display = False
        if result.stderr:
            self._appendOutput(result.stderr)
        if result.logPath:
            self.outputLines.append(f"Log: {result.logPath}")
            self._refreshProgress()

    def _finalizeProgress(self, result: RunnerResult) -> None:
        """Finalize parsed progress rows for a completed run.

        Args:
            result: Completed runner result.
        """

        now = monotonic()
        if result.returnCode == 130:
            if self.activePromptMessage is not None:
                self._recordPromptInteraction("aborted", aborted=True)
            self.pendingPromptMessage = None
            self.pendingPromptMode = None
            self.pendingPrettyOutputTitle = None
            self.pendingSyntheticTaskAfterPrompt = None
            self.suppressNextPromptResult = False
            self.suppressNextPromptTask = False
            self.progressParser.markAborted(now)
        else:
            if self.activePromptMessage is not None:
                if result.returnCode == 0:
                    self._recordPromptInteraction("continued")
                else:
                    self._recordPromptInteraction("failed", failed=True)
            self.pendingPromptMessage = None
            self.pendingPromptMode = None
            self.pendingPrettyOutputTitle = None
            self.pendingSyntheticTaskAfterPrompt = None
            self.suppressNextPromptResult = False
            self.suppressNextPromptTask = False
            self.progressParser.finalizePlay(now)
        self.progressRows = self.progressParser.rows(now)

    def _playbookNameText(self) -> str:
        """Build run title text.

        Returns:
            Playbook name with optional node context.
        """

        titleParts = [self.entry.displayName]
        if self.config.node:
            titleParts.append(self.config.node)
        return " ".join(titleParts)

    def _processProgressLine(self, line: str) -> None:
        """Update parsed progress state from one output line.

        Args:
            line: Runner output line.
        """

        now = monotonic()
        cleanLine = ANSI_PATTERN.sub("", line.rstrip("\n"))
        self._detectEventLogPath(cleanLine)
        self._detectRunLogPath(cleanLine)
        if self._suppressPromptImplementationLine(cleanLine, now):
            self.progressRows = self.progressParser.rows(now)
            return
        resultMatch = RESULT_PATTERN.match(cleanLine)
        activeRoleName = (
            self.progressParser.currentRole.name
            if self.progressParser.currentRole is not None
            else None
        )
        activeTaskName = (
            self.progressParser.currentTask.name
            if self.progressParser.currentTask is not None
            else None
        )
        self._detectPrettyOutputInclude(cleanLine)
        self.progressParser.processLine(cleanLine, now)
        if resultMatch and resultMatch.group(1) in {"ok", "changed"}:
            self._startSyntheticTaskAfterResult(
                activeRoleName,
                activeTaskName,
                now,
            )
        self._detectPrompt(cleanLine, now)
        self.progressRows = self.progressParser.rows(now)

    def _detectRunLogPath(self, line: str) -> None:
        """Capture the native Ansible log path from runner status output."""

        if not line.startswith(RUN_LOG_PREFIX):
            return
        self.runLogPath = Path(line.removeprefix(RUN_LOG_PREFIX)).expanduser()

    def _detectEventLogPath(self, line: str) -> None:
        """Capture the Ansible callback event log path from runner status output."""

        if not line.startswith(EVENT_LOG_PREFIX):
            return
        self.eventLogPath = Path(line.removeprefix(EVENT_LOG_PREFIX)).expanduser()
        self.eventLogOffset = 0

    def _processEventLogUpdates(self) -> None:
        """Process newly written Ansible callback events."""

        if self.eventLogPath is None or not self.eventLogPath.is_file():
            return
        try:
            with self.eventLogPath.open("r", encoding="utf-8") as eventLog:
                eventLog.seek(self.eventLogOffset)
                eventLines = eventLog.readlines()
                self.eventLogOffset = eventLog.tell()
        except OSError:
            return

        for line in eventLines:
            if not line.strip():
                continue
            try:
                eventRecord = json.loads(line)
            except json.JSONDecodeError:
                continue
            self._processEventRecord(eventRecord)

    def _processEventRecord(self, eventRecord: dict[str, object]) -> None:
        """Process one structured Ansible callback event."""

        eventName = str(eventRecord.get("event") or "")
        now = monotonic()
        if eventName == "play_start":
            play = eventRecord.get("play")
            if isinstance(play, dict):
                playName = str(play.get("name") or "").strip()
                if playName:
                    self.progressParser.processLine(
                        f"PLAY [{playName}] ********",
                        now,
                    )
            return
        if eventName == "include":
            include = eventRecord.get("include")
            if isinstance(include, dict):
                self._processIncludeEvent(include)
            return
        if eventName in {
            "runner_ok",
            "runner_failed",
            "runner_unreachable",
            "runner_skipped",
        }:
            self._recordPrettyOutputFromEvent(eventRecord)
            resultState = self._resultStateFromEvent(eventName)
            if resultState:
                self.progressParser.processLine(f"{resultState}: [localhost]", now)
            return
        if eventName != "task_start":
            return
        task = eventRecord.get("task")
        if not isinstance(task, dict):
            return
        if self._isNiceDisplayIncludeTask(task):
            self.pendingPrettyOutputTitle = self._niceDisplayTitleFromTask(task)
            return
        if self._isStructuralIncludeTask(task):
            return
        taskHeader = self._taskHeaderFromEvent(task)
        if taskHeader:
            self.progressParser.processLine(
                f"TASK [{taskHeader}] ********",
                now,
            )
        path = str(task.get("path") or "")
        if path.endswith("waitForInput.yaml:36") or "/waitForInput.yaml:" in path:
            self._startPromptFromEvent(task, "continue")
        elif (
            path.endswith("promptForInput.yaml:41")
            or "/promptForInput.yaml:" in path
        ):
            taskName = str(task.get("name") or "").lower()
            if "prompt for user input" in taskName:
                self._startPromptFromEvent(task, "text")

    def _processIncludeEvent(self, include: dict[str, object]) -> None:
        """Process one structured include callback event."""

        filename = str(include.get("filename") or "")
        if not self._isNiceDisplayPath(filename):
            return
        task = include.get("task")
        if isinstance(task, dict):
            self.pendingPrettyOutputTitle = self._niceDisplayTitleFromTask(task)
            return
        self.pendingPrettyOutputTitle = "Display"

    @staticmethod
    def _taskHeaderFromEvent(task: dict[str, object]) -> str:
        """Return an Ansible task header from callback task metadata."""

        taskName = str(task.get("name") or "").strip()
        roleName = str(task.get("role") or "").strip()
        if not taskName:
            return ""
        if not roleName or " : " in taskName:
            return taskName
        return f"{roleName} : {taskName}"

    @staticmethod
    def _isStructuralIncludeTask(task: dict[str, object]) -> bool:
        """Return whether a callback task is a structural include wrapper."""

        action = str(task.get("action") or "")
        return action.endswith("include_tasks")

    @classmethod
    def _isNiceDisplayIncludeTask(cls, task: dict[str, object]) -> bool:
        """Return whether a task directly references the display wrapper."""

        action = str(task.get("action") or "")
        path = str(task.get("path") or "")
        return action.endswith("include_tasks") and cls._isNiceDisplayPath(path)

    @staticmethod
    def _isNiceDisplayPath(path: str) -> bool:
        """Return whether a path points at the display wrapper."""

        return path.endswith("niceDisplay.yaml") or "/niceDisplay.yaml" in path

    @classmethod
    def _niceDisplayTitleFromTask(cls, task: dict[object, object]) -> str:
        """Return the display title implied by a wrapper task."""

        taskName = str(task.get("name") or "").strip()
        if " : " in taskName:
            taskName = taskName.split(" : ", 1)[1].strip()
        return taskName or "Display"

    def _detectPrettyOutputInclude(self, line: str) -> None:
        """Detect native output for the display wrapper include."""

        if not INCLUDED_PATTERN.match(line) or not self._isNiceDisplayPath(line):
            return
        if self.progressParser.currentTask is not None:
            self.pendingPrettyOutputTitle = self.progressParser.currentTask.name
            return
        self.pendingPrettyOutputTitle = "Display"

    @staticmethod
    def _resultStateFromEvent(eventName: str) -> str:
        """Return an Ansible result token for a callback result event."""

        if eventName == "runner_ok":
            return "ok"
        if eventName == "runner_failed":
            return "failed"
        if eventName == "runner_unreachable":
            return "unreachable"
        if eventName == "runner_skipped":
            return "skipping"
        return ""

    def _recordPrettyOutputFromEvent(self, eventRecord: dict[str, object]) -> None:
        """Record a pretty output block from a pending display wrapper result."""

        if self.pendingPrettyOutputTitle is None:
            return
        resultRecord = self._eventResultRecord(eventRecord)
        taskHeader = self._taskHeaderFromResultEvent(eventRecord, resultRecord)
        if resultRecord is None:
            return
        title = self._prettyPayloadTitle(resultRecord) or self.pendingPrettyOutputTitle
        body = self._prettyPayloadBody(self._prettyPayloadValue(resultRecord))
        if not title or not body:
            return
        self.progressParser.recordTaskOutput(
            taskHeader,
            title,
            body,
            hideTaskRow=True,
        )
        self.pendingPrettyOutputTitle = None

    @staticmethod
    def _eventResultRecord(
        eventRecord: dict[str, object],
    ) -> dict[str, object] | None:
        """Return callback result payload from supported event shapes."""

        resultRecord = eventRecord.get("result")
        if isinstance(resultRecord, dict):
            return resultRecord
        rawResultRecord = eventRecord.get("res")
        if isinstance(rawResultRecord, dict):
            return rawResultRecord
        return None

    def _taskHeaderFromResultEvent(
        self,
        eventRecord: dict[str, object],
        resultRecord: dict[str, object] | None,
    ) -> str:
        """Return a task header from a result event."""

        if resultRecord is not None:
            task = resultRecord.get("task")
            if isinstance(task, dict):
                return self._taskHeaderFromEvent(task)
            if isinstance(task, str):
                return task.strip()
        task = eventRecord.get("task")
        if isinstance(task, dict):
            return self._taskHeaderFromEvent(task)
        if isinstance(task, str):
            return task.strip()
        return ""

    @classmethod
    def _prettyPayloadBody(cls, payload: object) -> str:
        """Format a supported pretty payload without reflowing text."""

        if isinstance(payload, str):
            return payload.rstrip("\n")
        if isinstance(payload, list):
            return "\n".join(str(item) for item in payload).rstrip("\n")
        if isinstance(payload, dict):
            return "\n".join(
                f"{key}: {value}" for key, value in payload.items()
            ).rstrip("\n")
        if payload is None:
            return ""
        return str(payload).rstrip("\n")

    @staticmethod
    def _prettyPayloadTitle(resultRecord: dict[str, object]) -> str:
        """Return a title embedded in a structured display payload."""

        title = resultRecord.get("title")
        if isinstance(title, str):
            return title.strip()
        msg = resultRecord.get("msg")
        if isinstance(msg, dict):
            msgTitle = msg.get("title")
            if isinstance(msgTitle, str):
                return msgTitle.strip()
        return ""

    @staticmethod
    def _prettyPayloadValue(resultRecord: dict[str, object]) -> object:
        """Return the display payload from a callback result record."""

        for key in ("display", "body", "msg"):
            value = resultRecord.get(key)
            if value is not None:
                if key == "msg" and isinstance(value, dict):
                    for nestedKey in ("display", "body", "msg", "payload"):
                        nestedValue = value.get(nestedKey)
                        if nestedValue is not None:
                            return nestedValue
                return value
        return None

    def _startPromptFromEvent(
        self,
        task: dict[object, object],
        mode: PromptMode,
    ) -> None:
        """Start an active prompt from a callback task event."""

        if self.activePromptMessage is not None:
            return
        message = self._latestPromptMessageFromLog() or self._promptMessageFromTask(
            task,
            mode,
        )
        self._startPrompt(message, monotonic(), fromInclude=True, mode=mode)

    def _promptMessageFromTask(
        self,
        task: dict[object, object],
        mode: PromptMode,
    ) -> str:
        """Return a prompt fallback message from a callback task event."""

        taskName = str(task.get("name") or "")
        if " : " in taskName:
            taskName = taskName.split(" : ", 1)[1]
        promptTitle = self._promptTitleFromTaskName(taskName)
        if promptTitle is not None:
            return promptTitle or self._defaultPromptMessage(mode)
        if taskName:
            return taskName
        return self._defaultPromptMessage(mode)

    def _detectPrompt(self, line: str, now: float) -> None:
        """Detect Ansible pause/wait prompt tasks.

        Args:
            line: Cleaned runner output line.
            now: Timestamp for the prompt start.
        """

        if INCLUDED_PATTERN.match(line):
            includePromptMode = self._promptModeFromIncludeLine(line)
            if self.pendingPromptMessage is not None or includePromptMode is not None:
                mode = self.pendingPromptMode or includePromptMode or "continue"
                self._startPrompt(
                    self.pendingPromptMessage or self._defaultPromptMessage(mode),
                    now,
                    fromInclude=True,
                    mode=mode,
                )
                self.pendingPromptMessage = None
                self.pendingPromptMode = None
            return

        taskMatch = TASK_HEADER_PATTERN.match(line)
        if not taskMatch:
            return

        taskHeader = taskMatch.group(1)
        taskParts = taskHeader.split(" : ", 1)
        roleName = taskParts[0].lower() if len(taskParts) == 2 else ""
        taskName = taskParts[-1]
        normalizedTask = taskName.lower()
        isPauseRole = roleName == "pause"
        promptTitle = self._promptTitleFromTaskName(taskName)
        promptTitleMode = self._promptModeFromTaskName(taskName)
        isPromptInclude = self._isContinuePromptInclude(roleName, normalizedTask)
        isPromptTask = "wait for user input" in normalizedTask
        isTextPromptTask = self._isTextPromptTask(roleName, normalizedTask)
        if promptTitleMode is not None and not isPromptTask and not isTextPromptTask:
            self.pendingPromptMessage = (
                promptTitle
                if promptTitle is not None
                else self._defaultPromptMessage(promptTitleMode)
            )
            self.pendingPromptMode = promptTitleMode
            return
        if isPauseRole and isPromptInclude and not isPromptTask:
            self.pendingPromptMessage = taskName
            self.pendingPromptMode = "continue"
            return
        if isPromptTask and self.activePromptMessage is not None:
            self.progressParser.suppressActiveTask(now)
            return
        if isTextPromptTask and self.activePromptMessage is not None:
            self.progressParser.suppressActiveTask(now)
            return
        if isPauseRole and isPromptInclude:
            self.pendingPromptMessage = taskName
            self.pendingPromptMode = "continue"
            return
        if self._isTextPromptInclude(roleName, normalizedTask):
            self.pendingPromptMessage = taskName
            self.pendingPromptMode = "text"
            return
        if isPromptTask and self.suppressNextPromptTask:
            self.suppressNextPromptTask = False
            self.progressParser.suppressActiveTask(now)
            return
        if isTextPromptTask and self.suppressNextPromptTask:
            self.suppressNextPromptTask = False
            self.progressParser.suppressActiveTask(now)
            return
        if not isPauseRole and not isPromptTask and not isTextPromptTask:
            self.pendingPromptMessage = None
            self.pendingPromptMode = None
            return

        self._startPrompt(
            self.pendingPromptMessage or taskName,
            now,
            fromInclude=False,
            mode="text" if isTextPromptTask else "continue",
        )
        self.pendingPromptMessage = None
        self.pendingPromptMode = None

    def _refreshProgress(self) -> None:
        """Render parsed progress rows."""

        if self.running:
            self._processEventLogUpdates()
            self._syncProgressFollowFromScroll()
            self.progressRows = self.progressParser.rows(monotonic())
            status = self.query_one("#run-status", Static)
            status.display = True
            status.update(f"Running  elapsed={self._runElapsedText()}")

        failure = self.query_one("#run-failure", Static)
        if self._shouldRenderFailureDetails():
            failure.display = True
            failure.update(self._renderFailurePanel())
        else:
            failure.display = False
            failure.update("")
        progress = self.query_one("#run-progress", Static)
        progress.update(self._renderProgress())
        self._refreshPromptPanel()
        if self.running and self.followProgress:
            self._scrollProgressToEnd()

    def _syncProgressFollowFromScroll(self) -> None:
        """Update progress follow mode from the current scroll position."""

        self.followProgress = self._progressScrollAtBottom()

    def _progressScrollAtBottom(self) -> bool:
        """Return whether the progress view is currently at the bottom."""

        progressScroll = self.query_one("#run-progress-scroll", VerticalScroll)
        return progressScroll.max_scroll_y <= 0 or progressScroll.is_vertical_scroll_end

    def _eventInProgressScroll(self, event: events.MouseEvent) -> bool:
        """Return whether a mouse event occurred inside the progress scroll area."""

        if event.screen_x is None or event.screen_y is None:
            return False
        progressScroll = self.query_one("#run-progress-scroll", VerticalScroll)
        return progressScroll.region.contains_point(
            (int(event.screen_x), int(event.screen_y))
        )

    def _scrollProgressToEnd(self) -> None:
        """Keep the live progress view pinned to the newest rows."""

        self.query_one("#run-progress-scroll", VerticalScroll).scroll_end(
            animate=False
        )

    def _completedHelpText(self) -> str:
        """Return key help for a completed run."""

        if self._hasPrettyOutput():
            return "Enter/Space/Esc back  y copy output  Fn-drag select ⌘C copy"
        return "Enter/Space/Esc back"

    def _hasPrettyOutput(self) -> bool:
        """Return whether the current progress rows include pretty output."""

        return any(row.output is not None for row in self.progressRows)

    def _prettyOutputClipboardText(self) -> str:
        """Return visible pretty output blocks as plain text."""

        blocks = []
        for row in self.progressRows:
            if row.output is None:
                continue
            blocks.append(f"{row.output.title}\n{row.output.body}".rstrip())
        return "\n\n".join(blocks)

    @staticmethod
    def _copyTextWithNativeTool(text: str) -> bool:
        """Copy text with an OS clipboard command when one is available."""

        command: list[str] | None = None
        if sys.platform == "darwin" and shutil.which("pbcopy"):
            command = ["pbcopy"]
        elif shutil.which("wl-copy"):
            command = ["wl-copy"]
        elif shutil.which("xclip"):
            command = ["xclip", "-selection", "clipboard"]
        elif shutil.which("xsel"):
            command = ["xsel", "--clipboard", "--input"]
        if command is None:
            return False
        try:
            subprocess.run(
                command,
                input=text,
                text=True,
                check=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        except (OSError, subprocess.CalledProcessError):
            return False
        return True

    def _renderProgress(self) -> Table | Text:
        """Build rich progress renderable for the run panel.

        Returns:
            Rich renderable representing parsed progress rows.
        """

        if not self.progressRows:
            if self.running:
                return Text("Waiting for Ansible progress ...", style="dim")
            return Text("No parsed Ansible progress was detected.", style="dim")

        table = Table.grid(expand=True, padding=(0, 2))
        table.add_column(no_wrap=True, overflow="ellipsis", ratio=1)
        table.add_column(justify="right", no_wrap=True, width=1)
        table.add_column(justify="right", no_wrap=True, width=9)
        for row in self.progressRows:
            if row.output is not None:
                table.add_row(self._prettyOutputPanel(row.output), Text(""), Text(""))
                continue
            table.add_row(
                self._rowLabel(row),
                Text(self._statusIcon(row.status), style=STATUS_STYLES[row.status]),
                Text(self._rowTimer(row), style="dim"),
            )
        return table

    @staticmethod
    def _prettyOutputPanel(output: PrettyOutput) -> Panel:
        """Render a pretty output block preserving its body text."""

        return Panel(
            Text(output.body),
            box=box.ROUNDED,
            border_style="cyan",
            title=Text(output.title, style="cyan"),
            title_align="left",
        )

    async def _handlePromptKey(self, event: events.Key) -> None:
        """Handle keyboard input while an Ansible prompt is active.

        Args:
            event: Key event emitted by Textual.
        """

        if event.key == "escape":
            self.action_cancel()
        elif self.activePromptMode == "continue" and event.key in {"enter", "space"}:
            self._submitPromptInput()
        elif self.activePromptMode == "text" and event.key == "enter":
            self._submitPromptInput()
        elif self.activePromptMode == "text" and event.key == "backspace":
            promptInput = self._promptInput()
            promptInput.value = promptInput.value[:-1]
        self._refreshProgress()

    def _startPrompt(
        self,
        message: str,
        now: float,
        fromInclude: bool,
        mode: PromptMode,
    ) -> None:
        """Start collecting input for an active Ansible prompt.

        Args:
            fromInclude: Whether the prompt came from an include wrapper.
            message: Prompt message to display.
            mode: Prompt handling mode.
            now: Timestamp for prompt start.
        """

        promptInput = self._promptInput()
        self.activePromptFromInclude = fromInclude
        self.activePromptInput = ""
        self.activePromptMessage = message
        self.activePromptMode = mode
        self.activePromptStart = now
        promptInput.value = ""
        promptInput.display = mode == "text"
        if mode == "text":
            promptInput.focus()
        else:
            self.focus()

    def _submitPromptInput(self) -> None:
        """Submit the active prompt input to Ansible."""

        promptInput = self.activePromptInput
        if self.activePromptMessage is not None:
            self._recordPromptInteraction("continued")
        self.runControl.sendInput(f"{promptInput}\n")

    def _recordPromptInteraction(
        self,
        value: str,
        aborted: bool = False,
        failed: bool = False,
    ) -> None:
        """Record and clear the active prompt interaction.

        Args:
            value: Interaction result text.
            aborted: Whether the interaction aborted the run.
            failed: Whether the interaction failed before completion.
        """

        if self.activePromptMessage is None:
            return
        duration = monotonic() - self.activePromptStart
        promptMessage = self.activePromptMessage
        self.progressParser.recordInteraction(
            self._promptInteractionSummary(promptMessage),
            value,
            duration,
            aborted=aborted,
            failed=failed,
        )
        if not aborted and not failed:
            self.pendingSyntheticTaskAfterPrompt = self._syntheticTaskAfterPrompt(
                promptMessage
            )
        if self.activePromptFromInclude:
            self.suppressNextPromptTask = True
        self.activePromptFromInclude = False
        self.activePromptInput = ""
        self.activePromptMessage = None
        self.activePromptMode = None
        self.activePromptStart = 0.0
        self._hidePromptPanel()
        self.focus()
        self.progressRows = self.progressParser.rows(monotonic())

    def _suppressPromptImplementationLine(self, line: str, now: float) -> bool:
        """Suppress internal prompt task output before it reaches the parser."""

        taskMatch = TASK_HEADER_PATTERN.match(line)
        if taskMatch and self.suppressNextPromptTask:
            taskHeader = taskMatch.group(1)
            taskParts = taskHeader.split(" : ", 1)
            roleName = taskParts[0].lower() if len(taskParts) == 2 else ""
            taskName = taskParts[-1].lower()
            if "wait for user input" in taskName or self._isTextPromptTask(
                roleName,
                taskName,
            ):
                self.suppressNextPromptTask = False
                self.suppressNextPromptResult = True
                return True

        resultMatch = RESULT_PATTERN.match(line)
        if self.suppressNextPromptResult and resultMatch:
            self.suppressNextPromptResult = False
            if resultMatch.group(1) in {"ok", "changed"}:
                self._startPendingSyntheticTask(now)
                return True
        return False

    def _startPendingSyntheticTask(self, now: float) -> None:
        """Start predicted post-prompt work, when one is known."""

        if self.pendingSyntheticTaskAfterPrompt is None:
            return
        taskHeader, aliases = self.pendingSyntheticTaskAfterPrompt
        self.pendingSyntheticTaskAfterPrompt = None
        self.progressParser.startSyntheticTask(taskHeader, now, aliases)

    def _startSyntheticTaskAfterResult(
        self,
        roleName: str | None,
        taskName: str | None,
        now: float,
    ) -> None:
        """Start predicted work after known quiet-before-header tasks."""

        if roleName != "createRPiImage" or taskName != "Set image path (remote)":
            return
        self.progressParser.startSyntheticTaskFromCurrentRole(
            "Copy image to remote host",
            now,
            aliases={"Copy image to remote host"},
        )

    def _syntheticTaskAfterPrompt(self, message: str) -> tuple[str, set[str]] | None:
        """Return predicted work that follows a known prompt message."""

        normalizedMessage = message.lower()
        currentRole = self.progressParser.currentRole
        if (
            currentRole is None
            or "about to write [" not in normalizedMessage
            or "] to [" not in normalizedMessage
        ):
            return None
        return (
            f"{currentRole.name} : Writing image to device",
            {f"{currentRole.name} : write image to device"},
        )

    def _refreshPromptPanel(self) -> None:
        """Refresh the active prompt input panel."""

        promptPanel = self.query_one("#run-prompt-panel", Container)
        promptInput = self._promptInput()
        if self.activePromptMessage is None:
            self._hidePromptPanel()
            return

        self._refreshPromptMessageFromLog()
        promptPanel.display = True
        self.query_one("#run-prompt-message", Static).update(
            Text(self.activePromptMessage)
        )
        if self.activePromptMode == "text":
            promptInput.display = True
            self.query_one("#run-prompt-help", Static).update(
                "Enter submit  Esc cancel"
            )
        else:
            promptInput.display = False
            self.query_one("#run-prompt-help", Static).update(
                "Enter/Space continue  Esc cancel"
            )

    def _hidePromptPanel(self) -> None:
        """Hide and clear the prompt input panel."""

        self.query_one("#run-prompt-panel", Container).display = False
        self.query_one("#run-prompt-message", Static).update("")
        self.query_one("#run-prompt-help", Static).update("")
        promptInput = self._promptInput()
        promptInput.value = ""
        promptInput.display = False

    def _promptInput(self) -> Input:
        """Return the prompt input widget."""

        return self.query_one("#run-prompt-input", Input)

    def _refreshPromptMessageFromLog(self) -> None:
        """Replace fallback prompt labels with native Ansible prompt text."""

        promptMessage = self._latestPromptMessageFromLog()
        if promptMessage:
            self.activePromptMessage = promptMessage

    def _latestPromptMessageFromLog(self) -> str | None:
        """Return the latest prompt message from the native Ansible log."""

        if self.runLogPath is None or not self.runLogPath.is_file():
            return None
        try:
            logText = self.runLogPath.read_text(encoding="utf-8", errors="replace")
        except OSError:
            return None

        lines = logText.splitlines()
        for index, line in reversed(list(enumerate(lines))):
            payload = self._ansibleLogPayload(line)
            if not self._isPromptMarker(payload):
                continue
            promptMessage = self._nextPromptLogMessage(lines[index + 1 :])
            if promptMessage:
                return promptMessage
            return None
        return None

    @staticmethod
    def _ansibleLogPayload(line: str) -> str:
        """Strip native Ansible log metadata from a log line."""

        match = ANSIBLE_LOG_RECORD_PATTERN.match(line)
        if match:
            return match.group(1).strip()
        return line.strip()

    @classmethod
    def _nextPromptLogMessage(cls, lines: list[str]) -> str | None:
        """Return prompt text lines after a native Ansible prompt marker."""

        promptLines: list[str] = []
        for line in lines:
            if ANSIBLE_LOG_RECORD_PATTERN.match(line):
                break
            payload = cls._ansibleLogPayload(line)
            if not payload and not promptLines:
                continue
            promptLines.append(cls._cleanPromptMessage(payload))
        message = "\n".join(promptLines).strip()
        return message or None

    @staticmethod
    def _isPromptMarker(payload: str) -> bool:
        """Return whether a native log payload marks an Ansible prompt."""

        return (
            payload.startswith("[")
            and payload.endswith("]")
            and (
                ": wait for user input" in payload
                or ": prompt for user input" in payload
            )
        )

    @staticmethod
    def _cleanPromptMessage(message: str) -> str:
        """Normalize Ansible prompt text for compact display."""

        return re.sub(r"\s+\(output is hidden\):?$", "", message).strip()

    @staticmethod
    def _promptInteractionSummary(message: str) -> str:
        """Return a compact one-line prompt message for progress rows."""

        for line in message.splitlines():
            summary = line.strip()
            if summary:
                return summary
        return message.strip()

    @classmethod
    def _promptTitleFromTaskName(cls, taskName: str) -> str | None:
        """Return the title after a nice prompt task prefix, when present."""

        strippedName = taskName.strip()
        normalizedName = strippedName.lower()
        for prefix in PROMPT_TITLE_PREFIXES:
            if normalizedName.startswith(prefix):
                return strippedName[len(prefix) :].strip()
        return None

    @classmethod
    def _promptModeFromTaskName(cls, taskName: str) -> PromptMode | None:
        """Return the prompt mode implied by a nice prompt task prefix."""

        normalizedName = taskName.strip().lower()
        for prefix, mode in PROMPT_TITLE_PREFIXES.items():
            if normalizedName.startswith(prefix):
                return cast(PromptMode, mode)
        return None

    @staticmethod
    def _isTextPromptTask(roleName: str, normalizedTask: str) -> bool:
        """Return whether a task is a supported text-input prompt."""

        if roleName == "promptforinput":
            return normalizedTask.startswith("prompt for ")
        return normalizedTask.startswith("prompt for ")

    @staticmethod
    def _isTextPromptInclude(roleName: str, normalizedTask: str) -> bool:
        """Return whether a task is a text-input include wrapper."""

        return roleName == "promptforinput" and normalizedTask.startswith("prompt for ")

    @staticmethod
    def _isContinuePromptInclude(roleName: str, normalizedTask: str) -> bool:
        """Return whether a task is a continue-prompt include wrapper."""

        if roleName != "pause":
            return False
        return (
            "wait of input" in normalizedTask
            or "wait for user input to continue" in normalizedTask
        )

    @staticmethod
    def _promptModeFromIncludeLine(line: str) -> PromptMode | None:
        """Return prompt mode implied by an included task path."""

        if "/waitForInput.yaml" in line:
            return "continue"
        if "/promptForInput.yaml" in line:
            return "text"
        return None

    @staticmethod
    def _defaultPromptMessage(mode: PromptMode) -> str:
        """Return a fallback prompt message when no wrapper label exists."""

        if mode == "text":
            return "prompt for user input"
        return "wait for user input"

    def _renderFailurePanel(self) -> Panel:
        """Render compact failure details.

        Returns:
            Rich panel with failure location and log path.
        """

        details = Text()
        details.append("failedAt  ", style="bold")
        details.append(f"{self._failedAtText()}\n", style="bright_white")
        details.append("elapsed   ", style="bold")
        details.append(f"{self._runElapsedText()}\n", style="bright_black")
        details.append("log       ", style="bold")
        details.append(str(self._displayLogPath()), style="bright_black")
        return Panel(
            details,
            border_style="red",
            title="✗ Failure",
            title_align="left",
        )

    def _shouldRenderFailureDetails(self) -> bool:
        """Return whether failure details should be displayed."""

        return (
            self.result is not None
            and self.result.returnCode not in {0, 130}
            and not self.running
        )

    def _displayLogPath(self) -> str:
        """Return a compact display path for the run log."""

        if self.result is None or self.result.logPath is None:
            return "unavailable"
        try:
            return str(self.result.logPath.relative_to(self.defaults.projectRoot))
        except ValueError:
            return str(self.result.logPath)

    def _failedAtText(self) -> str:
        """Return the deepest visible failed progress path."""

        failedRows = [row for row in self.progressRows if row.status == "failed"]
        if not failedRows:
            if self.result is not None and self.result.stderr:
                return self.result.stderr.removeprefix("ERROR: ").strip()
            return "unknown"
        return " / ".join(row.name for row in failedRows)

    def _runElapsedText(self) -> str:
        """Return elapsed run time for the whole playbook run."""

        if self.runStartTime <= 0:
            return "0:00"
        endTime = self.runEndTime or monotonic()
        elapsedSeconds = max(0, int(endTime - self.runStartTime))
        minutes, seconds = divmod(elapsedSeconds, 60)
        return f"{minutes}:{seconds:02d}"

    def _rowTimer(self, row: ProgressRow) -> str:
        """Return the row-specific progress timer."""

        return self._formatDuration(row.duration)

    @staticmethod
    def _formatDuration(duration: float) -> str:
        """Format a compact row duration.

        Args:
            duration: Duration in seconds.

        Returns:
            Bracketed duration text for the progress table.
        """

        if duration >= 60:
            minutes, seconds = divmod(int(duration), 60)
            return f"[{minutes}m {seconds:02d}s]"
        return f"[{max(0.0, duration):.1f}s]"

    @staticmethod
    def _rowLabel(row: ProgressRow) -> Text:
        """Build the left-hand progress tree label.

        Args:
            row: Parsed progress row.

        Returns:
            Tree label with an icon and display name.
        """

        if row.depth == 0:
            return Text(f"{row.icon} {row.name}")
        if row.depth == 1:
            return Text(f"   └─ {row.icon} {row.name}")
        return Text(f"      └─ {row.icon} {row.name}")

    def _statusIcon(self, status: str) -> str:
        """Return the status icon for a progress row.

        Args:
            status: Progress row status.

        Returns:
            Display icon for the status.
        """

        if status == "running":
            icon = SPINNER_FRAMES[self.spinnerIndex % len(SPINNER_FRAMES)]
            self.spinnerIndex += 1
            return icon
        return STATUS_ICONS[status]

    def _runPlaybook(self) -> None:
        """Run the selected playbook through the command runner."""

        argv = buildRunnerArgv(self.config)
        options = AnsibleCommandRunner.parseOptions(argv)
        runner = self.runnerFactory(self.defaults)
        result = runner.runPlaybook(
            self.entry.path,
            "",
            options,
            echoOutput=False,
            outputHandler=self._appendOutputFromThread,
            runControl=self.runControl,
        )
        self.app.call_from_thread(self._finishRun, result)
