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
from textual.widgets import Footer, Header

from ansibleRunner.defaults import RuntimeDefaults
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

    #playbook-menu {
        align: center top;
        height: 1fr;
        width: 100%;
    }

    #playbook-panel {
        border: round cyan;
        height: auto;
        max-height: 90%;
        padding: 1 2;
        width: 92%;
    }

    #playbook-title {
        color: cyan;
        margin-bottom: 1;
        text-style: bold;
    }

    #playbook-table {
        height: auto;
        max-height: 24;
    }

    #playbook-help {
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
        yield PlaybookMenuScreen(self.defaults)
        yield Footer()


def runTui(defaults: RuntimeDefaults) -> int:
    """Run the Textual TUI.

    Args:
        defaults: Resolved project runtime defaults.

    Returns:
        Process exit code.
    """

    result = AnsibleRunnerTui(defaults).run()
    return int(result or 0)
