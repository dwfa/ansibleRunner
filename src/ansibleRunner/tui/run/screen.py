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
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal
from textual.widgets import RichLog, Static

from ansibleRunner.defaults import RuntimeDefaults
from ansibleRunner.playbooks.models import PlaybookConfig, PlaybookEntry
from ansibleRunner.playbooks.playbookConfig import buildRunnerArgv
from ansibleRunner.runner import AnsibleCommandRunner, RunnerResult


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
        Binding("escape", "back", "Back"),
        Binding("q", "back", "Back"),
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
        self.runnerFactory = runnerFactory or self._defaultRunnerFactory

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
            yield Static("q/Esc back", id="run-help")

    def on_mount(self) -> None:
        """Start the playbook run after mount."""

        self.focus()
        self.run_worker(self._runPlaybook, thread=True)

    async def action_back(self) -> None:
        """Return to the launch screen."""

        await self.onBack()

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
        status = self.query_one("#run-status", Static)
        if result.returnCode == 0:
            status.update("Finished: success")
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
        )
        self.app.call_from_thread(self._finishRun, result)
