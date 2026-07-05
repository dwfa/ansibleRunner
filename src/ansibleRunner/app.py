##############################################################################
# Application and menu orchestration for ansibleRunner.
#
# USAGE:
#   main(projectRoot, argv)
#
# WORKFLOW:
#   1. Resolve project-local runtime defaults.
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


def buildParser() -> argparse.ArgumentParser:
    """Build the application argument parser.

    Returns:
        Configured parser for ansibleRunner command-line options.
    """

    parser = argparse.ArgumentParser(
        prog="ansibleRunner",
        description="Run project-local Ansible management workflows.",
    )
    parser.add_argument(
        "--project-root",
        dest="projectRoot",
        type=Path,
        default=None,
        help="Project root containing playbooks, logs, and state.",
    )
    parser.add_argument(
        "--list-defaults",
        dest="listDefaults",
        action="store_true",
        help="Print resolved log and state defaults, then exit.",
    )
    return parser


class AnsibleRunnerApp:
    """Coordinates menu flow and command execution for a project root."""

    def __init__(self, projectRoot: Path, defaults: RuntimeDefaults | None = None) -> None:
        """Initialize the application for a project root.

        Args:
            projectRoot: Root directory for project-local logs and state.
            defaults: Optional pre-resolved runtime defaults.
        """

        self.defaults = defaults or RuntimeDefaults.forProject(projectRoot)

    def run(self, argv: Sequence[str] | None = None) -> int:
        """Run the selected application workflow.

        Args:
            argv: Optional command-line arguments excluding the executable name.

        Returns:
            Process exit code for the selected workflow.
        """

        parser = buildParser()
        args = parser.parse_args(list(argv or ()))

        if args.projectRoot is not None:
            self.defaults = RuntimeDefaults.forProject(args.projectRoot)

        if args.listDefaults:
            self._printDefaults()
            return 0

        self._printDefaults()
        return 0

    def _printDefaults(self) -> None:
        """Print the resolved project-local runtime defaults."""

        print(f"projectRoot={self.defaults.projectRoot}")
        print(f"logDir={self.defaults.logDir}")
        print(f"stateDir={self.defaults.stateDir}")


def main(projectRoot: str | Path, argv: Sequence[str] | None = None) -> int:
    """Run ansibleRunner for a project.

    This is the stable handoff point for project-specific wrappers such as
    `rpiMgmt`. Wrappers should resolve their own project root and pass it here.

    Args:
        projectRoot: Project root supplied by a thin project wrapper.
        argv: Optional command-line arguments excluding the executable name.

    Returns:
        Process exit code from the application workflow.
    """

    app = AnsibleRunnerApp(Path(projectRoot))
    return app.run(argv)
