##############################################################################
# Playbook configuration screen.
#
# USAGE:
#   ConfigureScreen(defaults, entry, onDone)
#
# Copyright 2026 Douglas WF Acheson (dwfa@dwfa.ca)
# Licensed under Apache License 2.0. See LICENSE.md for details.
#
# Version: 1.0
# Date: July 11, 2026
##############################################################################

"""Playbook configuration screen."""

from __future__ import annotations

import shlex
from collections.abc import Awaitable, Callable
from dataclasses import replace
from typing import Any

from textual import events
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal
from textual.widgets import DataTable, Static

from ansibleRunner.defaults import RuntimeDefaults
from ansibleRunner.playbooks.configFields import CONFIG_FIELDS
from ansibleRunner.playbooks.models import ConfigField, PlaybookConfig, PlaybookEntry
from ansibleRunner.playbooks.playbookConfig import (
    defaultPlaybookConfig,
    loadPlaybookConfigs,
    savePlaybookConfigs,
)


DoneHandler = Callable[[], Awaitable[None]]
SaveHandler = Callable[[PlaybookConfig], Awaitable[None]]


class ConfigureTable(DataTable[str]):
    """Data table that routes Enter to the configure screen."""

    def check_consume_key(self, key: str, character: str | None) -> bool:
        """Return whether inline node editing consumes a key.

        Args:
            key: Key identifier.
            character: Printable character, if any.

        Returns:
            True when the configure table is editing the node row.
        """

        screen = self._configureScreen()
        return screen.textEditValue is not None and (
            character is not None
            or key in {"backspace", "delete", "end", "enter", "escape", "home", "left", "right"}
        )

    def action_select_cursor(self) -> None:
        """Request edit handling for the selected row."""

        screen = self._configureScreen()
        if screen.textEditValue is not None:
            screen.commitTextEdit()
            return
        screen.action_edit_selected()

    def on_key(self, event: events.Key) -> None:
        """Handle inline node edit keystrokes while the table has focus.

        Args:
            event: Key event from Textual.
        """

        screen = self._configureScreen()
        if screen.textEditValue is None:
            return

        event.stop()
        event.prevent_default()
        if event.key == "enter":
            screen.commitTextEdit()
        elif event.key == "escape":
            screen.cancelTextEdit()
        elif event.key == "backspace":
            screen.backspaceTextEdit()
        elif event.key == "delete":
            screen.deleteTextEdit()
        elif event.key == "home":
            screen.moveTextEditCursor(0)
        elif event.key == "end":
            screen.moveTextEditCursor(len(screen.textEditValue))
        elif event.key == "left":
            screen.moveTextEditCursor(screen.textEditCursor - 1)
        elif event.key == "right":
            screen.moveTextEditCursor(screen.textEditCursor + 1)
        elif event.character:
            screen.insertTextEdit(event.character)

    def _configureScreen(self) -> "ConfigureScreen":
        """Return the owning configure screen.

        Returns:
            Owning configure screen.
        """

        return self.query_ancestor("#configure-menu", ConfigureScreen)


class ConfigureScreen(Container):
    """Edit saved launch configuration for one playbook.

    Args:
        defaults: Resolved project runtime defaults.
        entry: Selected playbook entry.
        onDone: Callback that returns to the playbook menu.
    """

    BINDINGS = [
        Binding("left", "cycle_left", "Previous", priority=True),
        Binding("right", "cycle_right", "Next", priority=True),
        Binding("enter", "edit_selected", "Edit"),
        Binding("escape", "cancel", "Back"),
        Binding("q", "cancel", "Back"),
    ]

    def __init__(
        self,
        defaults: RuntimeDefaults,
        entry: PlaybookEntry,
        onDone: DoneHandler,
        fields: tuple[ConfigField, ...] | None = CONFIG_FIELDS,
        headingPrefix: str = "⚙ Configure",
        helpText: str = "↑/↓ move  ←/→ change  Enter edit  s save  q/Esc back",
        initialConfig: PlaybookConfig | None = None,
        onSave: SaveHandler | None = None,
        saveKey: str = "s",
    ) -> None:
        """Initialize the configure screen.

        Args:
            defaults: Resolved project runtime defaults.
            entry: Selected playbook entry.
            onDone: Callback that returns to the playbook menu.
            fields: Editable fields for this screen.
            headingPrefix: Prefix shown in the panel heading.
            helpText: Help text shown below the table.
            initialConfig: Optional initial config instead of persisted config.
            onSave: Optional custom save callback.
            saveKey: Keyboard key used to save or apply changes.
        """

        super().__init__(id="configure-menu")
        self.configPath = defaults.stateDir / "playbookConfig.json"
        self.entry = entry
        self.fields = fields or CONFIG_FIELDS
        self.headingPrefix = headingPrefix
        self.helpText = helpText
        self.onDone = onDone
        self.onSave = onSave
        self.saveKey = saveKey
        self.textEditCursor = 0
        self.textEditField: ConfigField | None = None
        self.textEditValue: str | None = None
        self.workingConfig = initialConfig or self._loadConfig()

    def compose(self) -> ComposeResult:
        """Compose the configure panel.

        Yields:
            Textual widgets for editing a playbook configuration.
        """

        with Container(id="configure-panel"):
            with Horizontal(id="configure-heading"):
                yield Static(self.headingPrefix, id="configure-prefix")
                yield Static(self._playbookNameText(), id="configure-title")
                yield Static(self.entry.title, id="configure-description")
            yield ConfigureTable(id="configure-table")
            yield Static(self.helpText, id="configure-help")

    def on_mount(self) -> None:
        """Populate the configure table after mount."""

        table = self.query_one("#configure-table", ConfigureTable)
        table.cursor_type = "row"
        table.zebra_stripes = True
        table.add_columns("#", "Setting", "Value")
        self._refreshTable()
        table.focus()

    def action_cycle_left(self) -> None:
        """Cycle the selected setting backward."""

        if self.textEditValue is not None:
            self.moveTextEditCursor(self.textEditCursor - 1)
            return
        self._cycleSelectedField(-1)

    def action_cycle_right(self) -> None:
        """Cycle the selected setting forward."""

        if self.textEditValue is not None:
            self.moveTextEditCursor(self.textEditCursor + 1)
            return
        self._cycleSelectedField(1)

    async def action_cancel(self) -> None:
        """Return to the playbook menu without saving."""

        if self.textEditValue is not None:
            self.cancelTextEdit()
            return
        await self.onDone()

    async def action_save(self) -> None:
        """Save the current playbook configuration and return to the menu."""

        self.commitTextEdit()
        if self.onSave is not None:
            await self.onSave(self.workingConfig)
            return

        configs = loadPlaybookConfigs(self.configPath)
        configs[self.entry.name] = self.workingConfig
        savePlaybookConfigs(self.configPath, configs)
        self.notify(f"Saved configuration for {self.entry.name}.", title="Saved")
        await self.onDone()

    def action_edit_selected(self) -> None:
        """Edit the selected field when it supports text entry."""

        field = self.selectedField()
        if field is None:
            return
        if field.kind in {"args", "string"}:
            self.textEditField = field
            self.textEditValue = self._editableText(field)
            self.textEditCursor = len(self.textEditValue)
            self._refreshTable()
            return
        self._cycleSelectedField(1)

    @property
    def nodeEditValue(self) -> str | None:
        """Return the active node edit value for legacy callers.

        Returns:
            Node edit value when the node row is being edited.
        """

        if self.textEditField and self.textEditField.key == "node":
            return self.textEditValue
        return None

    def selectedField(self) -> ConfigField | None:
        """Return the selected editable table field.

        Returns:
            Selected config field, or None if no field row is selected.
        """

        table = self.query_one("#configure-table", ConfigureTable)
        cursorRow = table.cursor_row
        if not (0 <= cursorRow < len(self.fields)):
            return None
        return self.fields[cursorRow]

    def _cycleSelectedField(self, direction: int) -> None:
        """Change the selected field value.

        Args:
            direction: Positive or negative cycle direction.
        """

        field = self.selectedField()
        if field is None:
            return

        currentValue = getattr(self.workingConfig, field.key)
        if field.kind in {"args", "string"}:
            return
        elif field.kind == "bool":
            self.workingConfig = replace(
                self.workingConfig,
                **{field.key: not bool(currentValue)},
            )
        elif field.kind == "choice":
            self.workingConfig = replace(
                self.workingConfig,
                **{field.key: self._cycleChoice(field, str(currentValue), direction)},
            )

        self._refreshTable()

    def _cycleChoice(self, field: ConfigField, value: str, direction: int) -> str:
        """Cycle a choice field.

        Args:
            field: Choice config field.
            value: Current field value.
            direction: Positive or negative cycle direction.

        Returns:
            Next choice value.
        """

        if not field.choices:
            return value
        try:
            index = field.choices.index(value)
        except ValueError:
            index = 0
        nextIndex = (index + direction) % len(field.choices)
        return field.choices[nextIndex]

    def _fieldValue(self, field: ConfigField) -> str:
        """Render a field value for the configure table.

        Args:
            field: Config field to render.

        Returns:
            Display value.
        """

        value: Any = getattr(self.workingConfig, field.key)
        if field.kind in {"args", "string"}:
            if self.textEditField == field and self.textEditValue is not None:
                return (
                    self.textEditValue[: self.textEditCursor]
                    + "█"
                    + self.textEditValue[self.textEditCursor :]
                )
            if field.kind == "args":
                return shlex.join(value) if value else ""
            return str(value) if value else ""
        if field.kind == "bool":
            return "yes" if value else "no"
        return str(value)

    def commitNodeEdit(self) -> None:
        """Commit the inline node edit value into working config."""

        if self.nodeEditValue is None:
            return
        self.commitTextEdit()

    def cancelNodeEdit(self) -> None:
        """Cancel the inline node edit."""

        if self.nodeEditValue is None:
            return
        self.cancelTextEdit()

    def updateNodeEditValue(self, value: str) -> None:
        """Update the inline node edit value.

        Args:
            value: Updated node value.
        """

        if self.nodeEditValue is None:
            return
        self.textEditValue = value
        self._refreshTable()

    def commitTextEdit(self) -> None:
        """Commit the active text edit field into working config."""

        if self.textEditField is None or self.textEditValue is None:
            return

        field = self.textEditField
        value = self.textEditValue.strip()
        if field.kind == "args":
            try:
                parsedValue = tuple(shlex.split(value))
            except ValueError:
                parsedValue = tuple(self.workingConfig.extraArgs)
            self.workingConfig = replace(self.workingConfig, **{field.key: parsedValue})
        else:
            self.workingConfig = replace(self.workingConfig, **{field.key: value})

        self.textEditField = None
        self.textEditValue = None
        self.textEditCursor = 0
        self._refreshTable()

    def cancelTextEdit(self) -> None:
        """Cancel the active text edit field."""

        if self.textEditValue is None:
            return
        self.textEditField = None
        self.textEditValue = None
        self.textEditCursor = 0
        self._refreshTable()

    def backspaceTextEdit(self) -> None:
        """Delete the character before the active text cursor."""

        if self.textEditValue is None or self.textEditCursor <= 0:
            return
        self.textEditValue = (
            self.textEditValue[: self.textEditCursor - 1]
            + self.textEditValue[self.textEditCursor :]
        )
        self.textEditCursor -= 1
        self._refreshTable()

    def deleteTextEdit(self) -> None:
        """Delete the character after the active text cursor."""

        if self.textEditValue is None or self.textEditCursor >= len(self.textEditValue):
            return
        self.textEditValue = (
            self.textEditValue[: self.textEditCursor]
            + self.textEditValue[self.textEditCursor + 1 :]
        )
        self._refreshTable()

    def insertTextEdit(self, value: str) -> None:
        """Insert text at the active text cursor.

        Args:
            value: Text to insert.
        """

        if self.textEditValue is None:
            return
        self.textEditValue = (
            self.textEditValue[: self.textEditCursor]
            + value
            + self.textEditValue[self.textEditCursor :]
        )
        self.textEditCursor += len(value)
        self._refreshTable()

    def moveTextEditCursor(self, position: int) -> None:
        """Move the active text cursor.

        Args:
            position: Requested cursor offset.
        """

        if self.textEditValue is None:
            return
        self.textEditCursor = max(0, min(position, len(self.textEditValue)))
        self._refreshTable()

    def updateTextEditValue(self, value: str) -> None:
        """Update the active text edit value.

        Args:
            value: Updated text value.
        """

        if self.textEditValue is None:
            return
        self.textEditValue = value
        self.textEditCursor = len(value)
        self._refreshTable()

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        """Handle Enter selection from the configure table.

        Args:
            event: Textual row-selected event.
        """

        event.stop()
        self.action_edit_selected()

    async def on_key(self, event: events.Key) -> None:
        """Handle inline node edit keystrokes.

        Args:
            event: Key event from Textual.
        """

        if self.textEditValue is None and event.key == self.saveKey:
            event.stop()
            event.prevent_default()
            await self.action_save()
            return

        if self.textEditValue is None:
            return

        event.stop()
        event.prevent_default()
        if event.key == "enter":
            self.commitTextEdit()
        elif event.key == "escape":
            self.cancelTextEdit()
        elif event.key == "backspace":
            self.backspaceTextEdit()
        elif event.key == "delete":
            self.deleteTextEdit()
        elif event.key == "home":
            self.moveTextEditCursor(0)
        elif event.key == "end":
            self.moveTextEditCursor(len(self.textEditValue))
        elif event.key == "left":
            self.moveTextEditCursor(self.textEditCursor - 1)
        elif event.key == "right":
            self.moveTextEditCursor(self.textEditCursor + 1)
        elif event.character:
            self.insertTextEdit(event.character)

    def _loadConfig(self) -> PlaybookConfig:
        """Load the saved config for the selected playbook.

        Returns:
            Saved config, or default config if none exists.
        """

        configs = loadPlaybookConfigs(self.configPath)
        return configs.get(self.entry.name, defaultPlaybookConfig())

    def _refreshTable(self) -> None:
        """Refresh the editable table values."""

        table = self.query_one("#configure-table", ConfigureTable)
        cursorRow = table.cursor_row
        table.clear(columns=False)
        for index, field in enumerate(self.fields, start=1):
            table.add_row(str(index), field.label, self._fieldValue(field), key=field.key)
        if self.fields:
            table.move_cursor(row=max(0, min(cursorRow, len(self.fields) - 1)))

    def _playbookNameText(self) -> str:
        """Build the playbook name title text.

        Returns:
            Playbook name with optional node context.
        """

        titleParts = [self.entry.displayName]
        if self.workingConfig.node:
            titleParts.append(self.workingConfig.node)
        return " ".join(titleParts)

    def _editableText(self, field: ConfigField) -> str:
        """Return editable text for a text-like config field.

        Args:
            field: Text-like config field.

        Returns:
            Editable field text.
        """

        value: Any = getattr(self.workingConfig, field.key)
        if field.kind == "args":
            return shlex.join(value) if value else ""
        return str(value)
