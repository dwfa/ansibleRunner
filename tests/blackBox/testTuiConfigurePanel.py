##############################################################################
# TUI configure panel black-box tests for ansibleRunner.
#
# USAGE:
#   python3 -m pytest tests/blackBox/testTuiConfigurePanel.py
#
# WORKFLOW:
#   1. Verify the Textual configure panel opens from the playbook menu.
#   2. Verify editable playbook configuration can be saved or canceled.
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
from textual.containers import Container, Horizontal
from textual.widgets import DataTable, Static

from ansibleRunner.defaults import RuntimeDefaults
from ansibleRunner.playbooks.models import PlaybookConfig
from ansibleRunner.playbooks.playbookConfig import (
    loadPlaybookConfigs,
    savePlaybookConfigs,
)
from ansibleRunner.tui.app import AnsibleRunnerTui
from ansibleRunner.tui.configure.screen import ConfigureScreen, ConfigureTable
from ansibleRunner.tui.playbooks.screen import PlaybookMenuScreen


def createPlaybook(projectRoot: Path, name: str = "site-pb") -> None:
    """Create a minimal playbook fixture.

    Args:
        projectRoot: Temporary project root.
        name: Playbook stem without suffix.
    """

    playbookDir = projectRoot / "playbooks"
    playbookDir.mkdir(exist_ok=True)
    (playbookDir / f"{name}.yaml").write_text(
        "# Configure DNS services\n---\n",
        encoding="utf-8",
    )


@pytest.mark.asyncio
async def testTuiConfigurePanelOpensForSelectedPlaybook(tmp_path: Path) -> None:
    """Verify configure opens for the highlighted playbook."""

    createPlaybook(tmp_path)
    defaults = RuntimeDefaults.forProject(tmp_path)

    async with AnsibleRunnerTui(defaults).run_test() as pilot:
        menu = pilot.app.query_one("#playbook-menu", PlaybookMenuScreen)

        await menu.action_configure()

        configureMenu = pilot.app.query_one("#configure-menu", ConfigureScreen)
        configureHeading = pilot.app.query_one("#configure-heading", Horizontal)
        configurePanel = pilot.app.query_one("#configure-panel", Container)
        configurePrefix = pilot.app.query_one("#configure-prefix", Static)
        configureTitle = pilot.app.query_one("#configure-title", Static)
        configureDescription = pilot.app.query_one("#configure-description", Static)
        table = pilot.app.query_one("#configure-table", DataTable)

        assert configureMenu.entry.name == "site-pb"
        assert configureHeading.id == "configure-heading"
        assert configurePanel.id == "configure-panel"
        assert str(configurePrefix.content) == "⚙ Configure"
        assert str(configureTitle.content) == "site"
        assert str(configureDescription.content) == "Configure DNS services"
        assert table.row_count == 6
        assert table.get_cell_at((0, 1)) == "Node"
        assert table.get_cell_at((0, 2)) == ""
        assert table.get_cell_at((1, 1)) == "Output level"
        assert table.get_cell_at((1, 2)) == "role"


@pytest.mark.asyncio
async def testTuiConfigurePanelShowsNodeBesidePlaybookName(tmp_path: Path) -> None:
    """Verify saved node context appears beside the playbook name."""

    createPlaybook(tmp_path)
    defaults = RuntimeDefaults.forProject(tmp_path)
    savePlaybookConfigs(
        defaults.stateDir / "playbookConfig.json",
        {"site-pb": PlaybookConfig(node="defN")},
    )

    async with AnsibleRunnerTui(defaults).run_test() as pilot:
        await pilot.press("c")
        configureTitle = pilot.app.query_one("#configure-title", Static)
        table = pilot.app.query_one("#configure-table", DataTable)

        assert str(configureTitle.content) == "site defN"
        assert configureTitle.parent.id == "configure-heading"
        assert not list(pilot.app.query("#node-editor"))
        assert table.get_cell_at((0, 2)) == "defN"


@pytest.mark.asyncio
async def testTuiConfigurePanelEditsNodeHost(tmp_path: Path) -> None:
    """Verify node can be edited inline from the config table."""

    createPlaybook(tmp_path)
    defaults = RuntimeDefaults.forProject(tmp_path)

    async with AnsibleRunnerTui(defaults).run_test() as pilot:
        await pilot.press("c")
        configureMenu = pilot.app.query_one("#configure-menu", ConfigureScreen)
        table = pilot.app.query_one("#configure-table", DataTable)

        configureMenu.action_edit_selected()
        assert table.get_cell_at((0, 2)) == "█"
        await pilot.press("d", "e", "f", "N", "enter")

        assert configureMenu.nodeEditValue is None
        assert table.get_cell_at((0, 2)) == "defN"


@pytest.mark.asyncio
async def testTuiConfigurePanelEnterStartsInlineNodeEdit(tmp_path: Path) -> None:
    """Verify pressing Enter starts node editing in the selected row."""

    createPlaybook(tmp_path)
    defaults = RuntimeDefaults.forProject(tmp_path)

    async with AnsibleRunnerTui(defaults).run_test() as pilot:
        await pilot.press("c")
        configureMenu = pilot.app.query_one("#configure-menu", ConfigureScreen)
        table = pilot.app.query_one("#configure-table", ConfigureTable)

        await pilot.press("enter")
        assert configureMenu.nodeEditValue == ""
        assert table.get_cell_at((0, 2)) == "█"
        await pilot.press("d")
        assert table.get_cell_at((0, 2)) == "d█"
        await pilot.press("n", "s", "enter")

        assert configureMenu.nodeEditValue is None
        assert table.get_cell_at((0, 2)) == "dns"


@pytest.mark.asyncio
async def testTuiConfigurePanelEditKeepsExistingNodeVisible(tmp_path: Path) -> None:
    """Verify editing an existing node keeps its value visible."""

    createPlaybook(tmp_path)
    defaults = RuntimeDefaults.forProject(tmp_path)
    savePlaybookConfigs(
        defaults.stateDir / "playbookConfig.json",
        {"site-pb": PlaybookConfig(node="preinstaller")},
    )

    async with AnsibleRunnerTui(defaults).run_test() as pilot:
        await pilot.press("c")
        table = pilot.app.query_one("#configure-table", ConfigureTable)

        await pilot.press("enter")

        assert table.get_cell_at((0, 2)) == "preinstaller█"


@pytest.mark.asyncio
async def testTuiConfigurePanelArrowsDoNotEditNode(tmp_path: Path) -> None:
    """Verify left/right do not open or mutate node editing."""

    createPlaybook(tmp_path)
    defaults = RuntimeDefaults.forProject(tmp_path)

    async with AnsibleRunnerTui(defaults).run_test() as pilot:
        await pilot.press("c")
        configureMenu = pilot.app.query_one("#configure-menu", ConfigureScreen)
        table = pilot.app.query_one("#configure-table", DataTable)

        configureMenu.action_cycle_right()
        configureMenu.action_cycle_left()

        assert configureMenu.nodeEditValue is None
        assert table.get_cell_at((0, 2)) == ""


@pytest.mark.asyncio
async def testTuiConfigurePanelCyclesEditableValues(tmp_path: Path) -> None:
    """Verify configure fields can be changed in the panel."""

    createPlaybook(tmp_path)
    defaults = RuntimeDefaults.forProject(tmp_path)

    async with AnsibleRunnerTui(defaults).run_test() as pilot:
        menu = pilot.app.query_one("#playbook-menu", PlaybookMenuScreen)
        await menu.action_configure()
        configureMenu = pilot.app.query_one("#configure-menu", ConfigureScreen)
        table = pilot.app.query_one("#configure-table", DataTable)

        table.move_cursor(row=1)
        configureMenu.action_cycle_right()
        table.move_cursor(row=2)
        configureMenu.action_cycle_right()

        assert table.get_cell_at((1, 2)) == "task"
        assert table.get_cell_at((2, 2)) == "yes"


@pytest.mark.asyncio
async def testTuiConfigurePanelSavePersistsAndRefreshesMenu(tmp_path: Path) -> None:
    """Verify saving configure writes state and returns to refreshed menu."""

    createPlaybook(tmp_path)
    defaults = RuntimeDefaults.forProject(tmp_path)

    async with AnsibleRunnerTui(defaults).run_test() as pilot:
        menu = pilot.app.query_one("#playbook-menu", PlaybookMenuScreen)
        await menu.action_configure()
        configureMenu = pilot.app.query_one("#configure-menu", ConfigureScreen)
        table = pilot.app.query_one("#configure-table", DataTable)

        configureMenu.action_edit_selected()
        await pilot.press("d", "n", "s", "enter")
        table.move_cursor(row=1)
        configureMenu.action_cycle_right()
        table.move_cursor(row=2)
        configureMenu.action_cycle_right()
        await configureMenu.action_save()

        configs = loadPlaybookConfigs(defaults.stateDir / "playbookConfig.json")
        refreshedTable = pilot.app.query_one("#playbook-table", DataTable)

        assert configs["site-pb"].debug is True
        assert configs["site-pb"].node == "dns"
        assert configs["site-pb"].outputLevel == "task"
        assert refreshedTable.get_cell_at((0, 3)) == "-d -n dns --output-level task"


@pytest.mark.asyncio
async def testTuiConfigurePanelCancelDoesNotPersist(tmp_path: Path) -> None:
    """Verify cancel returns to the menu without writing state."""

    createPlaybook(tmp_path)
    defaults = RuntimeDefaults.forProject(tmp_path)

    async with AnsibleRunnerTui(defaults).run_test() as pilot:
        menu = pilot.app.query_one("#playbook-menu", PlaybookMenuScreen)
        await menu.action_configure()
        configureMenu = pilot.app.query_one("#configure-menu", ConfigureScreen)

        configureMenu.action_edit_selected()
        await pilot.press("d")
        await configureMenu.action_cancel()

        assert pilot.app.query_one("#configure-menu", ConfigureScreen)
        assert configureMenu.nodeEditValue is None
        await configureMenu.action_cancel()

        assert pilot.app.query_one("#playbook-menu", PlaybookMenuScreen)
        assert not (defaults.stateDir / "playbookConfig.json").exists()


@pytest.mark.asyncio
async def testTuiConfigurePanelKeyboardFlow(tmp_path: Path) -> None:
    """Verify keyboard commands open, edit, and leave configure."""

    createPlaybook(tmp_path)
    defaults = RuntimeDefaults.forProject(tmp_path)

    async with AnsibleRunnerTui(defaults).run_test() as pilot:
        await pilot.press("c")
        configureMenu = pilot.app.query_one("#configure-menu", ConfigureScreen)
        table = pilot.app.query_one("#configure-table", DataTable)

        assert pilot.app.query_one("#configure-description", Static).parent.id == (
            "configure-heading"
        )
        await pilot.press("down")
        await pilot.press("right")
        await pilot.press("down")
        await pilot.press("right")

        assert table.get_cell_at((1, 2)) == "task"
        assert table.get_cell_at((2, 2)) == "yes"

        await pilot.press("q")

        assert pilot.app.query_one("#playbook-menu", PlaybookMenuScreen)
        assert configureMenu.entry.name == "site-pb"
