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

from collections.abc import Awaitable, Callable

from rich.text import Text
from textual import events
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal
from textual.widgets import RichLog, Static

from ansibleRunner.defaults import RuntimeDefaults
from ansibleRunner.playbooks.models import PlaybookConfig, PlaybookEntry
from ansibleRunner.playbooks.playbookConfig import buildRunnerArgv
from ansibleRunner.runner import AnsibleCommandRunner, RunControl, RunnerResult


BackHandler = Callable[[], Awaitable[None]]
RunnerFactory = Callable[[RuntimeDefaults], AnsibleCommandRunner]


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
        Binding("c", "cancel", "Cancel", priority=True),
        Binding("ctrl+c", "cancel", "Cancel", priority=True),
        Binding("ctrl+z", "suspend_process", "Suspend", priority=True),
        Binding("escape", "back", "Back", priority=True),
        Binding("q", "back", "Back", priority=True),
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
        self.result: RunnerResult | None = None
        self.runControl = RunControl()
        self.runnerFactory = runnerFactory or self._defaultRunnerFactory
        self.running = False

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
            yield RichLog(id="run-log", wrap=True, highlight=False, markup=False)
            yield Static(
                "Enter input  c cancel  Ctrl-C exit  Ctrl-Z suspend  q/Esc cancel",
                id="run-help",
            )

    def on_mount(self) -> None:
        """Start the playbook run after mount."""

        self.focus()
        self.running = True
        self.run_worker(self._runPlaybook, thread=True)

    async def action_back(self) -> None:
        """Return to the launch screen."""

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
        elif event.key == "enter":
            event.stop()
            event.prevent_default()
            self.action_send_enter()
        elif event.key == "c":
            event.stop()
            event.prevent_default()
            self.action_cancel()
        elif event.key == "ctrl+z":
            event.stop()
            event.prevent_default()
            self.action_suspend_process()
        elif event.key in {"escape", "q"}:
            event.stop()
            event.prevent_default()
            await self.action_back()

    def action_cancel(self) -> None:
        """Cancel the active run."""

        if not self.running:
            return
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

    def action_send_enter(self) -> None:
        """Send an Enter keypress to the running playbook."""

        if self.running:
            self.runControl.sendInput("\n")

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
        """Append runner output to the screen.

        Args:
            line: Output line from the runner.
        """

        log = self.query_one("#run-log", RichLog)
        log.write(line.rstrip("\n"), scroll_end=True)

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

        self.result = result
        self.running = False
        status = self.query_one("#run-status", Static)
        helpText = self.query_one("#run-help", Static)
        helpText.update("q/Esc back")
        if result.returnCode == 0:
            status.update("Finished: success")
        elif result.returnCode == 130:
            status.update("Finished: canceled")
        else:
            status.update(f"Finished: failed ({result.returnCode})")
        if result.stderr:
            self._appendOutput(result.stderr)
        if result.logPath:
            self._appendOutput(f"Log: {result.logPath}")

    def _playbookNameText(self) -> str:
        """Build run title text.

        Returns:
            Playbook name with optional node context.
        """

        titleParts = [self.entry.displayName]
        if self.config.node:
            titleParts.append(self.config.node)
        return " ".join(titleParts)

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
