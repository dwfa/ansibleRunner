##############################################################################
# Main playbook menu screen.
#
# USAGE:
#   PlaybookMenuScreen(defaults)
#
# Copyright 2026 Douglas WF Acheson (dwfa@dwfa.ca)
# Licensed under Apache License 2.0. See LICENSE.md for details.
#
# Version: 1.0
# Date: July 11, 2026
##############################################################################

"""Main playbook menu screen."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from pathlib import Path

from textual.app import ComposeResult
from textual.containers import Container
from textual.widgets import DataTable, Static

from ansibleRunner.defaults import RuntimeDefaults
from ansibleRunner.playbooks import discoverPlaybookEntries, loadPlaybookConfigs
from ansibleRunner.playbooks.models import PlaybookEntry


ConfigureHandler = Callable[[PlaybookEntry], Awaitable[None]]
LaunchHandler = Callable[[PlaybookEntry], Awaitable[None]]


class PlaybookMenuScreen(Container):
    """Display the project playbook menu.

    Args:
        defaults: Resolved project runtime defaults.
        onConfigure: Callback that opens playbook configuration.
        onLaunch: Callback that opens playbook launch review.
    """

    BINDINGS = [
        ("c", "configure", "Configure"),
    ]

    def __init__(
        self,
        defaults: RuntimeDefaults,
        onConfigure: ConfigureHandler | None = None,
        onLaunch: LaunchHandler | None = None,
    ) -> None:
        """Initialize the playbook menu screen.

        Args:
            defaults: Resolved project runtime defaults.
            onConfigure: Callback that opens playbook configuration.
            onLaunch: Callback that opens playbook launch review.
        """

        super().__init__(id="playbook-menu")
        self.defaults = defaults
        self.entries: list[PlaybookEntry] = []
        self.playbookRoot = self.defaults.projectRoot / "playbooks"
        self.currentDir = self.playbookRoot
        self.onConfigure = onConfigure
        self.onLaunch = onLaunch

    def compose(self) -> ComposeResult:
        """Compose the playbook menu.

        Yields:
            Textual widgets for the playbook menu.
        """

        with Container(id="playbook-panel"):
            yield Static("📋 Available playbooks", id="playbook-title")
            yield DataTable(id="playbook-table")
            yield Static(
                "↑/↓ move  Enter open/launch  c configure  q/Esc quit",
                id="playbook-help",
            )

    def on_mount(self) -> None:
        """Populate the playbook table after the screen mounts."""

        table = self.query_one("#playbook-table", DataTable)
        table.cursor_type = "row"
        table.zebra_stripes = True
        table.add_columns("#", "Playbook", "Title", "Last config")
        self._refreshTable(table)

        table.focus()

    def _refreshTable(self, table: DataTable) -> None:
        """Reload entries for the current directory.

        Args:
            table: Playbook table to repopulate.
        """

        self.entries = self._loadEntries()
        table.clear(columns=False)
        if not self.entries:
            table.add_row("-", "(none)", "No playbooks found", "(unset)")
            return

        for index, entry in enumerate(self.entries, start=1):
            marker = "▸" if entry.isDirectory else str(index)
            table.add_row(
                marker,
                entry.displayName,
                entry.title,
                entry.configSummary,
                key=f"{'dir' if entry.isDirectory else 'playbook'}:{entry.name}",
            )

    async def action_launch(self) -> None:
        """Open the launch review panel for the selected playbook."""

        selectedEntry = self.selectedEntry()
        if selectedEntry is None:
            self.notify("No playbook is selected.", severity="warning", title="Launch")
            return
        if selectedEntry.isDirectory:
            self.openDirectory(selectedEntry.path)
            return
        if self.onLaunch is None:
            self.notify("Launch flow is not wired.", title="Coming soon")
            return
        await self.onLaunch(selectedEntry)

    async def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        """Handle Enter selection from the playbook table.

        Args:
            event: Textual row-selected event.
        """

        event.stop()
        await self.action_launch()

    async def action_configure(self) -> None:
        """Open the configuration panel for the selected playbook."""

        selectedEntry = self.selectedEntry()
        if selectedEntry is None:
            self.notify("No playbook is selected.", severity="warning", title="Configure")
            return
        if selectedEntry.isDirectory:
            self.notify(
                "Select a playbook to configure.",
                severity="warning",
                title="Configure",
            )
            return
        if self.onConfigure is None:
            self.notify("Configure flow is not wired.", title="Coming soon")
            return
        await self.onConfigure(selectedEntry)

    def openDirectory(self, directory: Path) -> None:
        """Open a playbook directory in the table.

        Args:
            directory: Directory to display.
        """

        root = self.playbookRoot.resolve()
        target = directory.expanduser().resolve()
        if target != root and root not in target.parents:
            self.notify("Directory is outside playbooks.", severity="error", title="Open")
            return
        self.currentDir = target
        table = self.query_one("#playbook-table", DataTable)
        self._refreshTable(table)
        if self.entries:
            table.move_cursor(row=0)

    def selectedEntry(self) -> PlaybookEntry | None:
        """Return the currently highlighted playbook entry.

        Returns:
            Selected playbook entry, or None when the table has no playbooks.
        """

        table = self.query_one("#playbook-table", DataTable)
        cursorRow = table.cursor_row
        if not (0 <= cursorRow < len(self.entries)):
            return None
        return self.entries[cursorRow]

    def _loadEntries(self) -> list[PlaybookEntry]:
        """Load playbook entries for the current project.

        Returns:
            Playbook entries with display metadata and config summaries.
        """

        configPath = self.defaults.stateDir / "playbookConfig.json"
        configs = loadPlaybookConfigs(configPath)
        return discoverPlaybookEntries(self.playbookRoot, configs, self.currentDir)
