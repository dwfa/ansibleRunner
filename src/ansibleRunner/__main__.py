##############################################################################
# Module execution entry point for ansibleRunner.
#
# USAGE:
#   python3 -m ansibleRunner
#
# WORKFLOW:
#   1. Delegate to the installed command-line entry point.
#   2. Exit with the returned process code.
#
# Copyright 2026 Douglas WF Acheson (dwfa@dwfa.ca)
# Licensed under Apache License 2.0. See LICENSE.md for details.
#
# Version: 1.0
# Date: July 05, 2026
##############################################################################

"""Run ansibleRunner as a module."""

from ansibleRunner.cli import main

if __name__ == "__main__":
    raise SystemExit(main())
