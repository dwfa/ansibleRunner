##############################################################################
# TUI playbook panel black-box tests for ansibleRunner.
#
# USAGE:
#   python3 -m pytest tests/blackBox/testTuiPlaybookPanel.py
#
# WORKFLOW:
#   1. Verify the Textual playbook panel composes with discovered playbooks.
#
# Copyright 2026 Douglas WF Acheson (dwfa@dwfa.ca)
# Licensed under Apache License 2.0. See LICENSE.md for details.
#
# Version: 1.0
# Date: July 11, 2026
##############################################################################

from __future__ import annotations

from pathlib import Path

import pytest
from textual.containers import Container
from textual.widgets import DataTable

from ansibleRunner.defaults import RuntimeDefaults
from ansibleRunner.tui.app import AnsibleRunnerTui
from ansibleRunner.tui.playbooks.screen import PlaybookMenuScreen


@pytest.mark.asyncio
async def testTuiPlaybookPanelShowsDiscoveredPlaybooks(tmp_path: Path) -> None:
    """Verify the TUI playbook table is populated from project playbooks."""

    playbookDir = tmp_path / "playbooks"
    playbookDir.mkdir()
    playbook = playbookDir / "site-pb.yaml"
    playbook.write_text(
        "##############################################################################\n"
        "# Configure DNS services\n"
        "##############################################################################\n"
        "---\n",
        encoding="utf-8",
    )
    defaults = RuntimeDefaults.forProject(tmp_path)

    async with AnsibleRunnerTui(defaults).run_test() as pilot:
        menu = pilot.app.query_one("#playbook-menu", Container)
        panel = pilot.app.query_one("#playbook-panel", Container)
        table = pilot.app.query_one("#playbook-table", DataTable)

        assert menu.id == "playbook-menu"
        assert panel.id == "playbook-panel"
        assert table.row_count == 1
        assert table.get_cell_at((0, 1)) == "site"
        assert table.get_cell_at((0, 2)) == "Configure DNS services"


@pytest.mark.asyncio
async def testTuiPlaybookPanelSelectionFollowsCursor(tmp_path: Path) -> None:
    """Verify playbook actions resolve the highlighted row."""

    playbookDir = tmp_path / "playbooks"
    playbookDir.mkdir()
    (playbookDir / "first.yaml").write_text("# First playbook\n---\n", encoding="utf-8")
    (playbookDir / "second.yaml").write_text("# Second playbook\n---\n", encoding="utf-8")
    defaults = RuntimeDefaults.forProject(tmp_path)

    async with AnsibleRunnerTui(defaults).run_test() as pilot:
        menu = pilot.app.query_one("#playbook-menu", PlaybookMenuScreen)
        table = pilot.app.query_one("#playbook-table", DataTable)

        assert menu.selectedEntry() is not None
        assert menu.selectedEntry().name == "first"

        table.move_cursor(row=1)

        assert menu.selectedEntry() is not None
        assert menu.selectedEntry().name == "second"


@pytest.mark.asyncio
async def testTuiPlaybookPanelActionsNameSelection(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Verify launch and configure placeholders name the selected playbook."""

    playbookDir = tmp_path / "playbooks"
    playbookDir.mkdir()
    (playbookDir / "first.yaml").write_text("# First playbook\n---\n", encoding="utf-8")
    (playbookDir / "second.yaml").write_text("# Second playbook\n---\n", encoding="utf-8")
    defaults = RuntimeDefaults.forProject(tmp_path)
    messages: list[str] = []

    async with AnsibleRunnerTui(defaults).run_test() as pilot:
        menu = pilot.app.query_one("#playbook-menu", PlaybookMenuScreen)
        table = pilot.app.query_one("#playbook-table", DataTable)
        monkeypatch.setattr(
            menu,
            "notify",
            lambda message, **kwargs: messages.append(message),
        )

        table.move_cursor(row=1)
        menu.action_placeholder_launch()
        menu.action_placeholder_configure()

        assert messages == [
            "Launch flow for second is not wired in this slice.",
            "Configure flow for second is not wired in this slice.",
        ]


@pytest.mark.asyncio
async def testTuiPlaybookPanelEnterSelectsHighlightedRow(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Verify table row selection routes to the launch action."""

    playbookDir = tmp_path / "playbooks"
    playbookDir.mkdir()
    (playbookDir / "first.yaml").write_text("# First playbook\n---\n", encoding="utf-8")
    (playbookDir / "second.yaml").write_text("# Second playbook\n---\n", encoding="utf-8")
    defaults = RuntimeDefaults.forProject(tmp_path)
    messages: list[str] = []

    class FakeRowSelected:
        """Minimal row-selected event for direct handler testing."""

        def stop(self) -> None:
            """Stop event propagation."""

    async with AnsibleRunnerTui(defaults).run_test() as pilot:
        menu = pilot.app.query_one("#playbook-menu", PlaybookMenuScreen)
        table = pilot.app.query_one("#playbook-table", DataTable)
        monkeypatch.setattr(
            menu,
            "notify",
            lambda message, **kwargs: messages.append(message),
        )

        table.move_cursor(row=1)
        menu.on_data_table_row_selected(FakeRowSelected())

        assert messages == ["Launch flow for second is not wired in this slice."]
