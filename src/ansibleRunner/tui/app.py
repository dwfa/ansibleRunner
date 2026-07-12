##############################################################################
# Textual application shell for ansibleRunner.
#
# USAGE:
#   runTui(defaults)
#
# Copyright 2026 Douglas WF Acheson (dwfa@dwfa.ca)
# Licensed under Apache License 2.0. See LICENSE.md for details.
#
# Version: 1.0
# Date: July 11, 2026
##############################################################################

"""Textual application shell."""

from __future__ import annotations

from textual.app import App, ComposeResult
from textual.containers import Container
from textual.widgets import Footer, Header

from ansibleRunner.defaults import RuntimeDefaults
from ansibleRunner.playbooks.models import PlaybookEntry
from ansibleRunner.tui.configure.screen import ConfigureScreen
from ansibleRunner.tui.playbooks.screen import PlaybookMenuScreen


class AnsibleRunnerTui(App[int]):
    """Raspi-config-like Textual app shell for ansibleRunner.

    Args:
        defaults: Resolved project runtime defaults.
    """

    CSS = """
    Screen {
        align: center top;
    }

    #app-body {
        align: center top;
        height: 1fr;
        width: 100%;
    }

    #playbook-menu {
        align: center top;
        height: 1fr;
        width: 100%;
    }

    #configure-menu {
        align: center top;
        height: 1fr;
        width: 100%;
    }

    #playbook-panel,
    #configure-panel {
        border: round cyan;
        height: auto;
        max-height: 90%;
        padding: 1 2;
        width: 92%;
    }

    #playbook-title,
    #configure-prefix,
    #configure-title {
        color: cyan;
        margin-bottom: 1;
        text-style: bold;
    }

    #configure-description {
        color: $text-muted;
        margin-bottom: 1;
        margin-left: 2;
    }

    #configure-heading {
        height: auto;
    }

    #configure-prefix {
        width: 12;
    }

    #configure-title {
        width: auto;
        max-width: 28;
    }

    #configure-description {
        width: 1fr;
    }

    #playbook-table,
    #configure-table {
        height: auto;
        max-height: 24;
    }

    #playbook-help,
    #configure-help {
        color: $text-muted;
        margin-top: 1;
    }
    """

    BINDINGS = [
        ("escape", "quit", "Quit"),
        ("q", "quit", "Quit"),
    ]

    def __init__(self, defaults: RuntimeDefaults) -> None:
        """Initialize the TUI app.

        Args:
            defaults: Resolved project runtime defaults.
        """

        super().__init__()
        self.defaults = defaults
        self.title = "ansibleRunner"
        self.sub_title = str(defaults.projectRoot)

    def compose(self) -> ComposeResult:
        """Compose application-level chrome.

        Yields:
            Textual widgets for the app shell.
        """

        yield Header(show_clock=True)
        yield Container(id="app-body")
        yield Footer()

    async def on_mount(self) -> None:
        """Mount the initial playbook menu."""

        await self.showPlaybookMenu()

    async def showPlaybookMenu(self) -> None:
        """Show the main playbook menu."""

        body = self.query_one("#app-body", Container)
        await body.remove_children()
        await body.mount(PlaybookMenuScreen(self.defaults, self.showConfigureScreen))

    async def showConfigureScreen(self, entry: PlaybookEntry) -> None:
        """Show the configure panel for a playbook.

        Args:
            entry: Playbook selected from the main menu.
        """

        body = self.query_one("#app-body", Container)
        await body.remove_children()
        await body.mount(ConfigureScreen(self.defaults, entry, self.showPlaybookMenu))


def runTui(defaults: RuntimeDefaults) -> int:
    """Run the Textual TUI.

    Args:
        defaults: Resolved project runtime defaults.

    Returns:
        Process exit code.
    """

    result = AnsibleRunnerTui(defaults).run()
    return int(result or 0)
