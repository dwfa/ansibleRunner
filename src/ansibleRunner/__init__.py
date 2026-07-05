##############################################################################
# Public API exports for ansibleRunner.
#
# USAGE:
#   from ansibleRunner import main
#
# OUTPUT VARIABLES:
#   - main: Stable wrapper entry point for project-specific shims.
#
# Copyright 2026 Douglas WF Acheson (dwfa@dwfa.ca)
# Licensed under Apache License 2.0. See LICENSE.md for details.
#
# Version: 1.0
# Date: July 05, 2026
##############################################################################

"""Public API for ansibleRunner."""

from ansibleRunner.app import main

__all__ = ["main"]
