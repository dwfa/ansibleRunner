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
from collections.abc import Awaitable, Callable
from pathlib import Path
from time import monotonic
from typing import Literal, cast

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
        """Cancel the active run when a back key is pressed."""

        if self.running:
            self.action_cancel()

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
        helpText.update("Enter/Space back")
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

        if eventRecord.get("event") != "task_start":
            return
        task = eventRecord.get("task")
        if not isinstance(task, dict):
            return
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
        isPromptInclude = self._isContinuePromptInclude(roleName, normalizedTask)
        isPromptTask = "wait for user input" in normalizedTask
        isTextPromptTask = self._isTextPromptTask(roleName, normalizedTask)
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
            table.add_row(
                self._rowLabel(row),
                Text(self._statusIcon(row.status), style=STATUS_STYLES[row.status]),
                Text(self._rowTimer(row), style="dim"),
            )
        return table

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
        self.progressParser.recordInteraction(
            self.activePromptMessage,
            value,
            duration,
            aborted=aborted,
            failed=failed,
        )
        if not aborted and not failed:
            self.pendingSyntheticTaskAfterPrompt = self._syntheticTaskAfterPrompt(
                self.activePromptMessage
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
            promptLine = self._nextPromptLogLine(lines[index + 1 :])
            if promptLine:
                return promptLine
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
    def _nextPromptLogLine(cls, lines: list[str]) -> str | None:
        """Return the prompt text after a native Ansible prompt marker."""

        for line in lines:
            payload = cls._ansibleLogPayload(line)
            if not payload:
                continue
            if ANSIBLE_LOG_RECORD_PATTERN.match(line):
                return None
            return cls._cleanPromptMessage(payload)
        return None

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

        return re.sub(r"\s+\(output is hidden\):?$", "", message).rstrip(":").strip()

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
