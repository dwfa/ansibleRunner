##############################################################################
# Command-line entry point for ansibleRunner.
#
# USAGE:
#   ansibleRunner --project-root /path/to/project
#
# WORKFLOW:
#   1. Capture command-line arguments.
#   2. Use the current working directory as the default project root.
#   3. Delegate to the public application entry point.
#
# Copyright 2026 Douglas WF Acheson (dwfa@dwfa.ca)
# Licensed under Apache License 2.0. See LICENSE.md for details.
#
# Version: 1.0
# Date: July 05, 2026
##############################################################################

"""Command-line entrypoint."""

from __future__ import annotations

import sys
from pathlib import Path

from ansibleRunner.app import main as runApp


def main(argv: list[str] | None = None) -> int:
    """Run ansibleRunner from the installed console entry point.

    Args:
        argv: Optional command-line arguments excluding the executable name.

    Returns:
        Process exit code from the application workflow.
    """

    args = list(sys.argv[1:] if argv is None else argv)
    projectRoot = Path.cwd()
    return runApp(projectRoot, args)
