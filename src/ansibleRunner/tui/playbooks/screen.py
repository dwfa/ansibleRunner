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

from textual.app import ComposeResult
from textual.containers import Container
from textual.widgets import DataTable, Static

from ansibleRunner.defaults import RuntimeDefaults
from ansibleRunner.playbooks import discoverPlaybookEntries, loadPlaybookConfigs
from ansibleRunner.playbooks.models import PlaybookEntry


class PlaybookMenuScreen(Container):
    """Display the project playbook menu.

    Args:
        defaults: Resolved project runtime defaults.
    """

    BINDINGS = [
        ("c", "placeholder_configure", "Configure"),
    ]

    def __init__(self, defaults: RuntimeDefaults) -> None:
        """Initialize the playbook menu screen.

        Args:
            defaults: Resolved project runtime defaults.
        """

        super().__init__(id="playbook-menu")
        self.defaults = defaults
        self.entries: list[PlaybookEntry] = []

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
        """Show a placeholder launch notification for the first TUI slice."""

        selectedEntry = self.selectedEntry()
        if selectedEntry is None:
            self.notify("No playbook is selected.", severity="warning", title="Launch")
            return
        self.notify(
            f"Launch flow for {selectedEntry.name} is not wired in this slice.",
            title="Coming soon",
        )

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        """Handle Enter selection from the playbook table.

        Args:
            event: Textual row-selected event.
        """

        event.stop()
        self.action_placeholder_launch()

    def action_placeholder_configure(self) -> None:
        """Show a placeholder configure notification for the first TUI slice."""

        selectedEntry = self.selectedEntry()
        if selectedEntry is None:
            self.notify("No playbook is selected.", severity="warning", title="Configure")
            return
        self.notify(
            f"Configure flow for {selectedEntry.name} is not wired in this slice.",
            title="Coming soon",
        )

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
