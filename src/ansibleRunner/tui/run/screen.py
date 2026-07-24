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
from collections.abc import Awaitable, Callable
from time import monotonic
from typing import cast

from rich.console import Group
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from textual import events
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, VerticalScroll
from textual.widgets import Static

from ansibleRunner.defaults import RuntimeDefaults
from ansibleRunner.playbooks.models import PlaybookConfig, PlaybookEntry
from ansibleRunner.playbooks.playbookConfig import buildRunnerArgv
from ansibleRunner.progressParser import (
    ANSI_PATTERN,
    AnsibleProgressParser,
    INCLUDED_PATTERN,
    OutputLevel,
    ProgressRow,
)
from ansibleRunner.runner import AnsibleCommandRunner, RunControl, RunnerResult


BackHandler = Callable[[], Awaitable[None]]
RunnerFactory = Callable[[RuntimeDefaults], AnsibleCommandRunner]


TASK_HEADER_PATTERN = re.compile(r"^TASK \[(.+?)\] \*+\s*$")
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
        Binding("enter", "send_enter", "Enter", priority=True),
        Binding("space", "send_enter", "Space", priority=True),
        Binding("c", "cancel", "Cancel", priority=True),
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
        self.onBack = onBack
        self.progressParser = AnsibleProgressParser(
            cast(OutputLevel, self.config.outputLevel)
        )
        self.progressRows: list[ProgressRow] = []
        self.result: RunnerResult | None = None
        self.runControl = RunControl()
        self.runnerFactory = runnerFactory or self._defaultRunnerFactory
        self.activePromptFromInclude = False
        self.activePromptMessage: str | None = None
        self.activePromptStart: float = 0.0
        self.pendingPromptMessage: str | None = None
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
            yield Static(
                "Enter/Space continue  c/Esc cancel  Ctrl-C exit  Ctrl-Z suspend",
                id="run-help",
            )

    def on_mount(self) -> None:
        """Start the playbook run after mount."""

        self.focus()
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
                self._recordPromptInteraction("continued")
            self.runControl.sendInput("\n")
            self._refreshProgress()
            return
        await self.onBack()

    def action_suspend_process(self) -> None:
        """Suspend the TUI process using Textual's app-level handler."""

        self.app.action_suspend_process()

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
            self.suppressNextPromptTask = False
            self.progressParser.markAborted(now)
        else:
            if self.activePromptMessage is not None:
                self._recordPromptInteraction("continued")
            self.pendingPromptMessage = None
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
        self.progressParser.processLine(cleanLine, now)
        self._detectPrompt(cleanLine, now)
        self.progressRows = self.progressParser.rows(now)

    def _detectPrompt(self, line: str, now: float) -> None:
        """Detect Ansible pause/wait prompt tasks.

        Args:
            line: Cleaned runner output line.
            now: Timestamp for the prompt start.
        """

        if INCLUDED_PATTERN.match(line) and self.pendingPromptMessage is not None:
            self.activePromptMessage = self.pendingPromptMessage
            self.activePromptStart = now
            self.activePromptFromInclude = True
            self.pendingPromptMessage = None
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
        isPromptInclude = "wait of input" in normalizedTask
        isPromptTask = "wait for user input" in normalizedTask
        if isPauseRole and isPromptInclude and not isPromptTask:
            self.pendingPromptMessage = taskName
            return
        if isPromptTask and self.activePromptMessage is not None:
            return
        if isPromptTask and self.suppressNextPromptTask:
            self.suppressNextPromptTask = False
            return
        if not isPauseRole and not isPromptTask:
            self.pendingPromptMessage = None
            return

        self.activePromptMessage = self.pendingPromptMessage or taskName
        self.activePromptStart = now
        self.activePromptFromInclude = False
        self.pendingPromptMessage = None

    def _refreshProgress(self) -> None:
        """Render parsed progress rows."""

        if self.running:
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

    def _renderProgress(self) -> Group | Table | Text:
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
        if self.activePromptMessage is not None:
            return Group(table, self._renderPromptCard())
        return table

    def _recordPromptInteraction(self, value: str, aborted: bool = False) -> None:
        """Record and clear the active prompt interaction.

        Args:
            value: Interaction result text.
            aborted: Whether the interaction aborted the run.
        """

        if self.activePromptMessage is None:
            return
        duration = monotonic() - self.activePromptStart
        self.progressParser.recordInteraction(
            self.activePromptMessage,
            value,
            duration,
            aborted=aborted,
        )
        if self.activePromptFromInclude:
            self.suppressNextPromptTask = True
        self.activePromptFromInclude = False
        self.activePromptMessage = None
        self.activePromptStart = 0.0
        self.progressRows = self.progressParser.rows(monotonic())

    def _renderPromptCard(self) -> Panel:
        """Render the active prompt card.

        Returns:
            Rich prompt card renderable.
        """

        message = self.activePromptMessage or "Waiting for input"
        cardText = Text()
        cardText.append(f"{message}\n")
        cardText.append("Enter/Space continue   c/Esc cancel", style="bright_black")
        return Panel(
            cardText,
            border_style="green",
            title="💬 Input",
            title_align="center",
        )

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
    def _rowLabel(row: ProgressRow) -> str:
        """Build the left-hand progress tree label.

        Args:
            row: Parsed progress row.

        Returns:
            Tree label with an icon and display name.
        """

        if row.depth == 0:
            return f"{row.icon} {row.name}"
        if row.depth == 1:
            return f"   └─ {row.icon} {row.name}"
        return f"      └─ {row.icon} {row.name}"

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
