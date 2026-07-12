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

from textual.app import ComposeResult
from textual.containers import Container
from textual.widgets import DataTable, Static

from ansibleRunner.defaults import RuntimeDefaults
from ansibleRunner.playbooks import discoverPlaybookEntries, loadPlaybookConfigs
from ansibleRunner.playbooks.models import PlaybookEntry


ConfigureHandler = Callable[[PlaybookEntry], Awaitable[None]]


class PlaybookMenuScreen(Container):
    """Display the project playbook menu.

    Args:
        defaults: Resolved project runtime defaults.
        onConfigure: Callback that opens playbook configuration.
    """

    BINDINGS = [
        ("c", "configure", "Configure"),
    ]

    def __init__(
        self,
        defaults: RuntimeDefaults,
        onConfigure: ConfigureHandler | None = None,
    ) -> None:
        """Initialize the playbook menu screen.

        Args:
            defaults: Resolved project runtime defaults.
            onConfigure: Callback that opens playbook configuration.
        """

        super().__init__(id="playbook-menu")
        self.defaults = defaults
        self.entries: list[PlaybookEntry] = []
        self.onConfigure = onConfigure

    def compose(self) -> ComposeResult:
        """Compose the playbook menu.

        Yields:
            Textual widgets for the playbook menu.
        """

        with Container(id="playbook-panel"):
            yield Static("📋 Available playbooks", id="playbook-title")
            yield DataTable(id="playbook-table")
            yield Static(
                "↑/↓ move  Enter launch  c configure  q/Esc quit",
                id="playbook-help",
            )

    def on_mount(self) -> None:
        """Populate the playbook table after the screen mounts."""

        table = self.query_one("#playbook-table", DataTable)
        table.cursor_type = "row"
        table.zebra_stripes = True
        table.add_columns("#", "Playbook", "Title", "Last config")

        self.entries = self._loadEntries()
        if not self.entries:
            table.add_row("-", "(none)", "No playbooks found", "(unset)")
            table.focus()
            return

        for index, entry in enumerate(self.entries, start=1):
            table.add_row(
                str(index),
                entry.displayName,
                entry.title,
                entry.configSummary,
                key=entry.name,
            )

        table.focus()

    def action_placeholder_launch(self) -> None:
        """Handle launch selection until the launch flow is implemented."""

        selectedEntry = self.selectedEntry()
        if selectedEntry is None:
            self.notify("No playbook is selected.", severity="warning", title="Launch")
            return

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        """Handle Enter selection from the playbook table.

        Args:
            event: Textual row-selected event.
        """

        event.stop()
        self.action_placeholder_launch()

    async def action_configure(self) -> None:
        """Open the configuration panel for the selected playbook."""

        selectedEntry = self.selectedEntry()
        if selectedEntry is None:
            self.notify("No playbook is selected.", severity="warning", title="Configure")
            return
        if self.onConfigure is None:
            self.notify("Configure flow is not wired.", title="Coming soon")
            return
        await self.onConfigure(selectedEntry)

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

        playbookDir = self.defaults.projectRoot / "playbooks"
        configPath = self.defaults.stateDir / "playbookConfig.json"
        configs = loadPlaybookConfigs(configPath)
        return discoverPlaybookEntries(playbookDir, configs)
