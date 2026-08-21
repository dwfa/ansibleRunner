##############################################################################
# findDirUp lookup plugin
#
# Walks upward from a starting directory looking for a directory with a given
# name, and returns the absolute path to that directory. Stops at the filesystem
# root; raises AnsibleError if the target is not found.
#
# USAGE:
#   {{ lookup('findDirUp', '<targetName>', '<startDir>') }}
#
# EXAMPLES:
#   pbPath:   "{{ lookup('findDirUp', 'playbooks', inventory_dir) }}"
#   taskPath: "{{ lookup('findDirUp', 'tasks',     inventory_dir) }}"
#   dataPath: "{{ lookup('findDirUp', 'data',      inventory_dir) }}"
#
# Copyright 2026 Douglas WF Acheson (dwfa@dwfa.ca)
# Licensed under Apache License 2.0. See LICENSE.md for details.
#
# Version: 1.0
# Date: August 16, 2026
##############################################################################

from __future__ import annotations

from pathlib import Path

from ansible.errors import AnsibleError
from ansible.plugins.lookup import LookupBase


class LookupModule(LookupBase):
    """Search upward for a directory by name."""

    def run(self, terms, variables=None, **kwargs):
        """Return the first matching parent child directory."""

        if len(terms) < 2:
            raise AnsibleError(
                "findDirUp requires two positional args: targetName and startDir"
            )

        targetName = terms[0]
        startDir = Path(terms[1]).resolve()

        current = startDir
        while True:
            candidate = current / targetName
            if candidate.is_dir():
                return [str(candidate)]
            if current.parent == current:
                raise AnsibleError(
                    f"findDirUp: no directory named [{targetName}] found "
                    f"walking up from [{startDir}] to filesystem root."
                )
            current = current.parent
