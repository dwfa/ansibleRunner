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

from importlib.metadata import PackageNotFoundError, version as _packageVersion

from ansibleRunner.app import main

try:
    __version__ = _packageVersion("ansibleRunner")
except PackageNotFoundError:
    __version__ = "0.0.0+unknown"

__all__ = ["__version__", "main"]
