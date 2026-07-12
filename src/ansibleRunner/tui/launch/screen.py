##############################################################################
# Playbook launch review screen.
#
# USAGE:
#   LaunchScreen(defaults, entry, onBack, onConfigure)
#
# Copyright 2026 Douglas WF Acheson (dwfa@dwfa.ca)
# Licensed under Apache License 2.0. See LICENSE.md for details.
#
# Version: 1.0
# Date: July 12, 2026
##############################################################################

"""Playbook launch review screen."""

from __future__ import annotations

from collections.abc import Awaitable, Callable

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal
from textual.widgets import DataTable, Static

from ansibleRunner.defaults import RuntimeDefaults
from ansibleRunner.playbooks.models import PlaybookConfig, PlaybookEntry
from ansibleRunner.playbooks.playbookConfig import (
    buildRunnerArgv,
    defaultPlaybookConfig,
    loadPlaybookConfigs,
)


BackHandler = Callable[[], Awaitable[None]]
ConfigureHandler = Callable[[PlaybookEntry], Awaitable[None]]


class LaunchScreen(Container):
    """Review a playbook before execution.

    Args:
        defaults: Resolved project runtime defaults.
        entry: Selected playbook entry.
        onBack: Callback that returns to the playbook menu.
        onConfigure: Callback that opens saved configuration.
    """

    BINDINGS = [
        Binding("enter", "run_placeholder", "Run"),
        Binding("r", "run_placeholder", "Run"),
        Binding("e", "edit_once_placeholder", "Edit once"),
        Binding("c", "configure", "Configure"),
        Binding("escape", "back", "Back"),
        Binding("q", "back", "Back"),
    ]

    def __init__(
        self,
        defaults: RuntimeDefaults,
        entry: PlaybookEntry,
        onBack: BackHandler,
        onConfigure: ConfigureHandler,
    ) -> None:
        """Initialize the launch screen.

        Args:
            defaults: Resolved project runtime defaults.
            entry: Selected playbook entry.
            onBack: Callback that returns to the playbook menu.
            onConfigure: Callback that opens saved configuration.
        """

        super().__init__(id="launch-menu")
        self.config = self._loadConfig(defaults, entry)
        self.entry = entry
        self.onBack = onBack
        self.onConfigure = onConfigure

    def compose(self) -> ComposeResult:
        """Compose the launch review panel.

        Yields:
            Textual widgets for reviewing launch details.
        """

        with Container(id="launch-panel"):
            with Horizontal(id="launch-heading"):
                yield Static("▶ Launch", id="launch-prefix")
                yield Static(self._playbookNameText(), id="launch-title")
                yield Static(self.entry.title, id="launch-description")
            yield DataTable(id="launch-table")
            yield Static(
                "Enter/r run  e edit once  c configure  q/Esc back",
                id="launch-help",
            )

    def on_mount(self) -> None:
        """Populate launch review details."""

        table = self.query_one("#launch-table", DataTable)
        table.cursor_type = "row"
        table.show_header = False
        table.zebra_stripes = True
        table.add_columns("Item", "Value")
        table.add_row("Args", self._runnerArgvText())
        table.focus()

    async def action_back(self) -> None:
        """Return to the playbook menu."""

        await self.onBack()

    async def action_configure(self) -> None:
        """Open saved configuration for this playbook."""

        await self.onConfigure(self.entry)

    def action_edit_once_placeholder(self) -> None:
        """Show placeholder for edit-once launch configuration."""

        self.notify("Edit-once launch options are not wired yet.", title="Coming soon")

    def action_run_placeholder(self) -> None:
        """Show placeholder for playbook execution."""

        self.notify("Run execution is not wired yet.", title="Coming soon")

    def _loadConfig(
        self,
        defaults: RuntimeDefaults,
        entry: PlaybookEntry,
    ) -> PlaybookConfig:
        """Load saved launch configuration for a playbook.

        Args:
            defaults: Resolved project runtime defaults.
            entry: Selected playbook entry.

        Returns:
            Saved config, or default config when none exists.
        """

        configs = loadPlaybookConfigs(defaults.stateDir / "playbookConfig.json")
        return configs.get(entry.name, defaultPlaybookConfig())

    def _playbookNameText(self) -> str:
        """Build launch title text.

        Returns:
            Playbook name with optional node context.
        """

        titleParts = [self.entry.displayName]
        if self.config.node:
            titleParts.append(self.config.node)
        return " ".join(titleParts)

    def _runnerArgvText(self) -> str:
        """Build display text for the runner command arguments.

        Returns:
            Command-line arguments that would be passed to the runner.
        """

        argv = buildRunnerArgv(self.config)
        if not argv:
            return "(none)"
        return " ".join(argv)
