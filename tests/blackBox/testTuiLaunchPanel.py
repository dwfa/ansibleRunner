##############################################################################
# TUI launch panel black-box tests for ansibleRunner.
#
# USAGE:
#   python3 -m pytest tests/blackBox/testTuiLaunchPanel.py
#
# WORKFLOW:
#   1. Verify Enter from the playbook menu opens launch review.
#   2. Verify launch review displays saved configuration.
#
# Copyright 2026 Douglas WF Acheson (dwfa@dwfa.ca)
# Licensed under Apache License 2.0. See LICENSE.md for details.
#
# Version: 1.0
# Date: July 12, 2026
##############################################################################

from __future__ import annotations

from pathlib import Path

import pytest
from textual.containers import Container, Horizontal
from textual.widgets import DataTable, Static

from ansibleRunner.defaults import RuntimeDefaults
from ansibleRunner.playbooks.models import PlaybookConfig
from ansibleRunner.playbooks.playbookConfig import savePlaybookConfigs
from ansibleRunner.tui.app import AnsibleRunnerTui
from ansibleRunner.tui.configure.screen import ConfigureScreen
from ansibleRunner.tui.launch.screen import LaunchScreen
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
async def testTuiLaunchPanelOpensFromPlaybookEnter(tmp_path: Path) -> None:
    """Verify Enter from the playbook list opens launch review."""

    createPlaybook(tmp_path)
    defaults = RuntimeDefaults.forProject(tmp_path)

    async with AnsibleRunnerTui(defaults).run_test() as pilot:
        await pilot.press("enter")

        launchMenu = pilot.app.query_one("#launch-menu", LaunchScreen)
        launchHeading = pilot.app.query_one("#launch-heading", Horizontal)
        launchPanel = pilot.app.query_one("#launch-panel", Container)
        launchPrefix = pilot.app.query_one("#launch-prefix", Static)
        launchTitle = pilot.app.query_one("#launch-title", Static)
        launchDescription = pilot.app.query_one("#launch-description", Static)
        table = pilot.app.query_one("#launch-table", DataTable)

        assert launchMenu.entry.name == "site-pb"
        assert launchHeading.id == "launch-heading"
        assert launchPanel.id == "launch-panel"
        assert str(launchPrefix.content) == "▶ Launch"
        assert str(launchTitle.content) == "site"
        assert str(launchDescription.content) == "Configure DNS services"
        assert table.row_count == 1
        assert not table.show_header
        assert table.get_cell_at((0, 0)) == "Args"
        assert table.get_cell_at((0, 1)) == "--output-level role"


@pytest.mark.asyncio
async def testTuiLaunchPanelShowsSavedConfig(tmp_path: Path) -> None:
    """Verify launch review includes saved configuration details."""

    createPlaybook(tmp_path)
    defaults = RuntimeDefaults.forProject(tmp_path)
    savePlaybookConfigs(
        defaults.stateDir / "playbookConfig.json",
        {
            "site-pb": PlaybookConfig(
                debug=True,
                node="dns",
                outputLevel="task",
            )
        },
    )

    async with AnsibleRunnerTui(defaults).run_test() as pilot:
        await pilot.press("enter")
        launchTitle = pilot.app.query_one("#launch-title", Static)
        table = pilot.app.query_one("#launch-table", DataTable)

        assert str(launchTitle.content) == "site dns"
        assert table.row_count == 1
        assert table.get_cell_at((0, 0)) == "Args"
        assert table.get_cell_at((0, 1)) == "-d -n dns --output-level task"


@pytest.mark.asyncio
async def testTuiLaunchPanelBackReturnsToPlaybookList(tmp_path: Path) -> None:
    """Verify launch review can return to the playbook list."""

    createPlaybook(tmp_path)
    defaults = RuntimeDefaults.forProject(tmp_path)

    async with AnsibleRunnerTui(defaults).run_test() as pilot:
        await pilot.press("enter")
        launchMenu = pilot.app.query_one("#launch-menu", LaunchScreen)

        await launchMenu.action_back()

        assert pilot.app.query_one("#playbook-menu", PlaybookMenuScreen)


@pytest.mark.asyncio
async def testTuiLaunchPanelConfigureOpensConfigure(tmp_path: Path) -> None:
    """Verify launch review can jump to saved configuration."""

    createPlaybook(tmp_path)
    defaults = RuntimeDefaults.forProject(tmp_path)

    async with AnsibleRunnerTui(defaults).run_test() as pilot:
        await pilot.press("enter")
        launchMenu = pilot.app.query_one("#launch-menu", LaunchScreen)

        await launchMenu.action_configure()

        configureMenu = pilot.app.query_one("#configure-menu", ConfigureScreen)

        assert configureMenu.entry.name == "site-pb"


@pytest.mark.asyncio
async def testTuiLaunchPanelConfigureSaveReturnsToLaunch(tmp_path: Path) -> None:
    """Verify saving configure from launch returns to refreshed launch review."""

    createPlaybook(tmp_path)
    defaults = RuntimeDefaults.forProject(tmp_path)

    async with AnsibleRunnerTui(defaults).run_test() as pilot:
        await pilot.press("enter")
        launchMenu = pilot.app.query_one("#launch-menu", LaunchScreen)
        await launchMenu.action_configure()
        configureMenu = pilot.app.query_one("#configure-menu", ConfigureScreen)

        configureMenu.action_edit_selected()
        await pilot.press("d", "n", "s", "enter")
        await configureMenu.action_save()

        launchTitle = pilot.app.query_one("#launch-title", Static)
        table = pilot.app.query_one("#launch-table", DataTable)

        assert str(launchTitle.content) == "site dns"
        assert table.get_cell_at((0, 1)) == "-n dns --output-level role"
