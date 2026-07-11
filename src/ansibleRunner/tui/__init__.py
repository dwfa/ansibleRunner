##############################################################################
# Textual TUI package for ansibleRunner.
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

"""Textual TUI package."""

from ansibleRunner.tui.app import AnsibleRunnerTui, runTui

__all__ = ["AnsibleRunnerTui", "runTui"]
