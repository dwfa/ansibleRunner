##############################################################################
# getPyLauncherPath lookup plugin
#
# Returns the absolute path to the Python interpreter running ansible-playbook
# itself.
#
# Used by inventory to point a host at the launcher's venv Python without
# hard-coding a project-layout-dependent path, without assuming inventory
# location, and without requiring a launcher-set environment variable.
#
# USAGE:
#   ansible_python_interpreter: "{{ lookup('getPyLauncherPath') }}"
#
# Copyright 2026 Douglas WF Acheson (dwfa@dwfa.ca)
# Licensed under Apache License 2.0. See LICENSE.md for details.
#
# Version: 1.0
# Date: August 16, 2026
##############################################################################

from __future__ import annotations

import sys

from ansible.plugins.lookup import LookupBase


class LookupModule(LookupBase):
    """Return the launcher's Python interpreter path."""

    def run(self, terms, variables=None, **kwargs):
        """Return the interpreter path for the current ansible-playbook process."""

        return [sys.executable]
