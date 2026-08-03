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

from collections.abc import Awaitable, Callable

from rich.text import Text
from textual.app import App, ComposeResult
from textual.containers import Container
from textual.css.query import NoMatches
from textual.widgets import Footer, Header

from ansibleRunner.defaults import RuntimeDefaults
from ansibleRunner.playbooks.configFields import LAUNCH_CONFIG_FIELDS
from ansibleRunner.playbooks.models import ConfigField, PlaybookConfig, PlaybookEntry
from ansibleRunner.tui.configure.screen import ConfigureScreen, SaveHandler
from ansibleRunner.tui.launch.screen import LaunchScreen
from ansibleRunner.tui.playbooks.screen import PlaybookMenuScreen
from ansibleRunner.tui.run.screen import RunScreen


DoneHandler = Callable[[], Awaitable[None]]


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

    #launch-menu {
        align: center top;
        height: 1fr;
        width: 100%;
    }

    #run-menu {
        align: center top;
        height: 1fr;
        width: 100%;
    }

    #playbook-panel,
    #configure-panel,
    #launch-panel,
    #run-panel {
        border: round magenta;
        height: auto;
        max-height: 90%;
        padding: 1 2;
        width: 92%;
    }

    #run-panel {
        height: 90%;
    }

    #playbook-title,
    #configure-prefix,
    #configure-title,
    #launch-prefix,
    #launch-title,
    #run-prefix,
    #run-title {
        color: cyan;
        margin-bottom: 1;
        text-style: bold;
    }

    #configure-description {
        color: $text-muted;
        margin-bottom: 1;
        margin-left: 2;
    }

    #launch-description {
        color: $text-muted;
        margin-bottom: 1;
        margin-left: 2;
        width: 1fr;
    }

    #run-description {
        color: $text-muted;
        margin-bottom: 1;
        margin-left: 2;
        width: 1fr;
    }

    #configure-heading,
    #launch-heading,
    #run-heading,
    #run-args {
        height: auto;
    }

    #configure-prefix,
    #launch-prefix,
    #run-prefix {
        width: 12;
    }

    #configure-title,
    #launch-title,
    #run-title {
        width: auto;
        max-width: 28;
    }

    #configure-description {
        width: 1fr;
    }

    #playbook-table,
    #configure-table,
    #launch-table {
        height: auto;
        max-height: 24;
    }

    #run-args {
        margin-bottom: 1;
    }

    #run-args-label {
        text-style: bold;
        width: 6;
    }

    #run-args-value {
        width: 1fr;
    }

    #run-status {
        color: $text-muted;
        margin-bottom: 1;
    }

    #run-failure {
        display: none;
        height: auto;
        margin-bottom: 1;
        width: 100%;
    }

    #run-progress-scroll {
        background: $surface;
        height: 1fr;
        min-height: 10;
        padding: 1 1;
    }

    #run-progress {
        height: auto;
        width: 100%;
    }

    #run-prompt-panel {
        border: round green;
        display: none;
        height: auto;
        margin-top: 1;
        padding: 0 1;
        width: 100%;
    }

    #run-prompt-title {
        color: green;
        content-align: center middle;
        text-style: bold;
        width: 100%;
    }

    #run-prompt-message {
        text-style: bold;
    }

    #run-prompt-input {
        margin: 1 0 0 0;
        width: 100%;
    }

    #run-prompt-help {
        color: $text-muted;
    }

    #playbook-help,
    #configure-help,
    #launch-help,
    #run-help {
        color: $text-muted;
        margin-top: 1;
    }
    """

    BINDINGS = [
        ("ctrl+c", "interrupt_process", "Interrupt"),
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

    def action_interrupt_process(self) -> None:
        """Interrupt the active run or exit the app."""

        try:
            runScreen = self.query_one("#run-menu", RunScreen)
        except NoMatches:
            self.exit(return_code=130)
            return
        runScreen.action_interrupt_process()

    def action_help_quit(self) -> None:
        """Handle Textual's built-in Ctrl-C binding."""

        self.action_interrupt_process()

    async def showPlaybookMenu(self) -> None:
        """Show the main playbook menu."""

        body = self.query_one("#app-body", Container)
        await body.remove_children()
        await body.mount(
            PlaybookMenuScreen(
                self.defaults,
                self.showConfigureScreen,
                self.showLaunchScreen,
            )
        )

    async def showConfigureScreen(
        self,
        entry: PlaybookEntry,
        onDone: DoneHandler | None = None,
        fields: tuple[ConfigField, ...] | None = None,
        headingPrefix: str = "⚙ Configure",
        helpText: str = "↑/↓ move  ←/→ change  Enter edit  s save  q/Esc back",
        initialConfig: PlaybookConfig | None = None,
        onSave: SaveHandler | None = None,
        saveKey: str = "s",
    ) -> None:
        """Show the configure panel for a playbook.

        Args:
            entry: Playbook selected from the main menu.
            onDone: Optional callback for returning after configure.
            fields: Optional editable fields.
            headingPrefix: Prefix shown in the panel heading.
            helpText: Help text shown below the table.
            initialConfig: Optional initial config instead of persisted config.
            onSave: Optional custom save callback.
            saveKey: Keyboard key used to save or apply changes.
        """

        body = self.query_one("#app-body", Container)
        await body.remove_children()
        await body.mount(
            ConfigureScreen(
                self.defaults,
                entry,
                onDone or self.showPlaybookMenu,
                fields=fields,
                headingPrefix=headingPrefix,
                helpText=helpText,
                initialConfig=initialConfig,
                onSave=onSave,
                saveKey=saveKey,
            )
        )

    async def showLaunchScreen(
        self,
        entry: PlaybookEntry,
        config: PlaybookConfig | None = None,
        isEditOnce: bool = False,
    ) -> None:
        """Show the launch review panel for a playbook.

        Args:
            entry: Playbook selected from the main menu.
            config: Optional one-run launch config.
            isEditOnce: Whether config contains one-run overrides.
        """

        async def configureFromLaunch(configEntry: PlaybookEntry) -> None:
            """Open configure and return to launch afterward.

            Args:
                configEntry: Playbook entry to configure.
            """

            await self.showConfigureScreen(configEntry, lambda: self.showLaunchScreen(entry))

        async def editOnceFromLaunch(
            configEntry: PlaybookEntry,
            launchConfig: PlaybookConfig,
        ) -> None:
            """Open one-run launch configuration.

            Args:
                configEntry: Playbook entry to edit for one launch.
                launchConfig: Current launch configuration.
            """

            async def saveLaunchConfig(editedConfig: PlaybookConfig) -> None:
                """Return to launch with one-run configuration.

                Args:
                    editedConfig: One-run configuration from the editor.
                """

                self.notify(
                    f"Applied one-run options for {configEntry.name}.",
                    title="Edit once",
                )
                await self.showLaunchScreen(configEntry, editedConfig, isEditOnce=True)

            await self.showConfigureScreen(
                configEntry,
                lambda: self.showLaunchScreen(
                    configEntry,
                    launchConfig,
                    isEditOnce=isEditOnce,
                ),
                fields=LAUNCH_CONFIG_FIELDS,
                headingPrefix="✎ Edit once",
                helpText="↑/↓ move  ←/→ change  Enter edit  a apply  q/Esc back",
                initialConfig=launchConfig,
                onSave=saveLaunchConfig,
                saveKey="a",
            )

        async def runFromLaunch(
            runEntry: PlaybookEntry,
            launchConfig: PlaybookConfig,
            argsDisplay: str | Text,
        ) -> None:
            """Open the run screen for a launch configuration.

            Args:
                runEntry: Playbook entry to run.
                launchConfig: Launch configuration to execute.
                argsDisplay: Styled launch argument display text.
            """

            await self.showRunScreen(
                runEntry,
                launchConfig,
                argsDisplay,
                lambda: self.showLaunchScreen(runEntry, launchConfig, isEditOnce),
            )

        body = self.query_one("#app-body", Container)
        await body.remove_children()
        await body.mount(
            LaunchScreen(
                self.defaults,
                entry,
                self.showPlaybookMenu,
                configureFromLaunch,
                editOnceFromLaunch,
                runFromLaunch,
                config,
                isEditOnce,
            )
        )

    async def showRunScreen(
        self,
        entry: PlaybookEntry,
        config: PlaybookConfig,
        argsDisplay: str | Text,
        onBack: DoneHandler,
    ) -> None:
        """Show the playbook run screen.

        Args:
            entry: Playbook selected for execution.
            config: Launch configuration to execute.
            argsDisplay: Styled argument display text.
            onBack: Callback for returning after the run.
        """

        body = self.query_one("#app-body", Container)
        await body.remove_children()
        await body.mount(RunScreen(self.defaults, entry, config, argsDisplay, onBack))


def runTui(defaults: RuntimeDefaults) -> int:
    """Run the Textual TUI.

    Args:
        defaults: Resolved project runtime defaults.

    Returns:
        Process exit code.
    """

    result = AnsibleRunnerTui(defaults).run()
    return int(result or 0)
