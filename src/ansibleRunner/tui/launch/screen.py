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

import shlex
from collections.abc import Awaitable, Callable

from rich.text import Text
from textual import events
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
EditOnceHandler = Callable[[PlaybookEntry, PlaybookConfig], Awaitable[None]]
RunHandler = Callable[[PlaybookEntry, PlaybookConfig, str | Text], Awaitable[None]]


class LaunchTable(DataTable[str]):
    """Launch table that routes Enter to the launch screen."""

    async def action_select_cursor(self) -> None:
        """Start the run when Enter is pressed inside the table."""

        screen = self.query_ancestor("#launch-menu", LaunchScreen)
        await screen.action_run_placeholder()


class LaunchScreen(Container):
    """Review a playbook before execution.

    Args:
        defaults: Resolved project runtime defaults.
        entry: Selected playbook entry.
        onBack: Callback that returns to the playbook menu.
        onConfigure: Callback that opens saved configuration.
    """

    BINDINGS = [
        Binding("enter", "run_placeholder", "Run", priority=True),
        Binding("r", "run_placeholder", "Run", priority=True),
        Binding("e", "edit_once", "Edit once", priority=True),
        Binding("c", "configure", "Configure", priority=True),
        Binding("escape", "back", "Back", priority=True),
        Binding("q", "back", "Back", priority=True),
    ]
    can_focus = True

    def __init__(
        self,
        defaults: RuntimeDefaults,
        entry: PlaybookEntry,
        onBack: BackHandler,
        onConfigure: ConfigureHandler,
        onEditOnce: EditOnceHandler,
        onRun: RunHandler,
        config: PlaybookConfig | None = None,
        isEditOnce: bool = False,
    ) -> None:
        """Initialize the launch screen.

        Args:
            defaults: Resolved project runtime defaults.
            entry: Selected playbook entry.
            onBack: Callback that returns to the playbook menu.
            onConfigure: Callback that opens saved configuration.
            onEditOnce: Callback that opens one-run configuration.
            onRun: Callback that starts a playbook run.
            config: Optional launch config override.
            isEditOnce: Whether config contains one-run overrides.
        """

        super().__init__(id="launch-menu")
        self.savedConfig = self._loadConfig(defaults, entry)
        self.config = config or self.savedConfig
        self.entry = entry
        self.isEditOnce = isEditOnce
        self.onBack = onBack
        self.onConfigure = onConfigure
        self.onEditOnce = onEditOnce
        self.onRun = onRun

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
            yield LaunchTable(id="launch-table")
            yield Static(
                "Enter/r run  e edit once  c configure  q/Esc back",
                id="launch-help",
            )

    def on_mount(self) -> None:
        """Populate launch review details."""

        table = self.query_one("#launch-table", LaunchTable)
        table.cursor_type = "none"
        table.show_header = False
        table.zebra_stripes = True
        table.add_columns("Item", "Value")
        table.add_row("Args", self._runnerArgvDisplay())
        self.focus()

    async def action_back(self) -> None:
        """Return to the playbook menu."""

        await self.onBack()

    async def on_key(self, event: events.Key) -> None:
        """Handle launch keys even when a child widget has focus.

        Args:
            event: Key event emitted by Textual.
        """

        if event.key in {"enter", "r"}:
            event.stop()
            event.prevent_default()
            await self.action_run_placeholder()
        elif event.key == "e":
            event.stop()
            event.prevent_default()
            await self.action_edit_once()
        elif event.key == "c":
            event.stop()
            event.prevent_default()
            await self.action_configure()
        elif event.key in {"escape", "q"}:
            event.stop()
            event.prevent_default()
            await self.action_back()

    async def action_configure(self) -> None:
        """Open saved configuration for this playbook."""

        await self.onConfigure(self.entry)

    async def action_edit_once(self) -> None:
        """Open one-run launch configuration."""

        await self.onEditOnce(self.entry, self.config)

    async def action_run_placeholder(self) -> None:
        """Start playbook execution."""

        await self.onRun(self.entry, self.config, self._runnerArgvDisplay())

    async def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        """Start the run when the launch table row is selected.

        Args:
            event: Data table row selection event.
        """

        event.stop()
        await self.action_run_placeholder()

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

    def _runnerArgvDisplay(self) -> str | Text:
        """Build styled display content for the runner arguments.

        Returns:
            Plain argument text, with one-run argument groups highlighted.
        """

        if not self.isEditOnce:
            return self._runnerArgvText()

        return self._styledRunnerArgv()

    def _appendArgGroup(
        self,
        text: Text,
        parts: list[str],
        isEditOnce: bool,
    ) -> None:
        """Append a command argument group to display text.

        Args:
            text: Rich text buffer receiving the argument group.
            parts: Argument parts in this logical group.
            isEditOnce: Whether this group is only for the current run.
        """

        if not parts:
            return
        if text.plain:
            text.append(" ")
        style = "bold cyan" if isEditOnce else ""
        text.append(shlex.join(parts), style=style)

    def _styledRunnerArgv(self) -> Text:
        """Build argument display text with only one-run groups highlighted.

        Returns:
            Rich text for the final launch arguments.
        """

        text = Text()
        self._appendArgGroup(
            text,
            ["-d"] if self.config.debug else [],
            self.config.debug != self.savedConfig.debug,
        )
        self._appendArgGroup(
            text,
            ["-c"] if self.config.check else [],
            self.config.check != self.savedConfig.check,
        )
        self._appendArgGroup(
            text,
            ["-s"] if self.config.syntaxCheck else [],
            self.config.syntaxCheck != self.savedConfig.syntaxCheck,
        )
        self._appendArgGroup(
            text,
            ["-t"] if self.config.listTasks else [],
            self.config.listTasks != self.savedConfig.listTasks,
        )
        self._appendArgGroup(
            text,
            ["-n", self.config.node] if self.config.node else [],
            self.config.node != self.savedConfig.node,
        )
        self._appendArgGroup(
            text,
            ["--output-level", self.config.outputLevel],
            self.config.outputLevel != self.savedConfig.outputLevel,
        )
        self._appendArgGroup(
            text,
            list(self.config.extraArgs),
            self.config.extraArgs != self.savedConfig.extraArgs,
        )
        if not text.plain:
            text.append("(none)")
        return text
