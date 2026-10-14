##############################################################################
# Application and menu orchestration for ansibleRunner.
#
# USAGE:
#   main(arPath, argv, pbPath)
#
# WORKFLOW:
#   1. Resolve ansibleRunner runtime defaults.
#   2. Parse application-level command-line options.
#   3. Run the selected menu or diagnostic workflow.
#
# Copyright 2026 Douglas WF Acheson (dwfa@dwfa.ca)
# Licensed under Apache License 2.0. See LICENSE.md for details.
#
# Version: 1.0
# Date: July 05, 2026
##############################################################################

"""Application and menu orchestration."""

from __future__ import annotations

import argparse
from collections.abc import Sequence
from pathlib import Path

from ansibleRunner.defaults import RuntimeDefaults
from ansibleRunner.tui import runTui


def buildParser() -> argparse.ArgumentParser:
    """Build the application argument parser.

    Returns:
        Configured parser for ansibleRunner command-line options.
    """

    parser = argparse.ArgumentParser(
        prog="ansibleRunner",
        description="Run project-local Ansible management workflows.",
    )
    from ansibleRunner import __version__

    parser.add_argument(
        "-V",
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
    )
    parser.add_argument(
        "--arPath",
        dest="arPath",
        type=Path,
        default=None,
        help="ansibleRunner path containing logs, state, and default playbooks.",
    )
    parser.add_argument(
        "--pbPath",
        dest="pbPath",
        type=Path,
        default=None,
        help="Playbook root to show and run instead of arPath/playbooks.",
    )
    parser.add_argument(
        "--listDefaults",
        dest="listDefaults",
        action="store_true",
        help="Print resolved log and state defaults, then exit.",
    )
    return parser


class AnsibleRunnerApp:
    """Coordinates menu flow and command execution for an arPath."""

    def __init__(
        self,
        arPath: Path,
        defaults: RuntimeDefaults | None = None,
        pbPath: Path | None = None,
    ) -> None:
        """Initialize the application for an ansibleRunner path.

        Args:
            arPath: Directory for ansibleRunner logs, state, and command cwd.
            defaults: Optional pre-resolved runtime defaults.
            pbPath: Optional playbook root override.
        """

        self.defaults = defaults or RuntimeDefaults.forArPath(arPath, pbPath)

    def run(self, argv: Sequence[str] | None = None) -> int:
        """Run the selected application workflow.

        Args:
            argv: Optional command-line arguments excluding the executable name.

        Returns:
            Process exit code for the selected workflow.
        """

        parser = buildParser()
        args = parser.parse_args(list(argv or ()))

        arPath = args.arPath or self.defaults.arPath
        pbPath = args.pbPath or self.defaults.pbPath
        if args.arPath is not None or args.pbPath is not None:
            self.defaults = RuntimeDefaults.forArPath(arPath, pbPath)

        if args.listDefaults:
            self._printDefaults()
            return 0

        return runTui(self.defaults)

    def _printDefaults(self) -> None:
        """Print the resolved project-local runtime defaults."""

        print(f"arPath={self.defaults.arPath}")
        print(f"pbPath={self.defaults.pbPath}")
        print(f"logDir={self.defaults.logDir}")
        print(f"stateDir={self.defaults.stateDir}")


def main(
    arPath: str | Path | None = None,
    argv: Sequence[str] | None = None,
    pbPath: str | Path | None = None,
) -> int:
    """Run ansibleRunner for an ansibleRunner path.

    This is the stable handoff point for project-specific wrappers such as
    `rpiMgmt`. Wrappers should resolve their own arPath and pass it here.

    Args:
        arPath: ansibleRunner path supplied by a thin project wrapper.
        argv: Optional command-line arguments excluding the executable name.
        pbPath: Optional playbook root override.

    Returns:
        Process exit code from the application workflow.
    """

    runnerPath = Path.cwd() if arPath is None else Path(arPath)
    app = AnsibleRunnerApp(runnerPath, pbPath=Path(pbPath) if pbPath else None)
    return app.run(argv)
