##############################################################################
# Default runtime paths for project-local logs and state.
#
# USAGE:
#   RuntimeDefaults.forProject(projectRoot)
#
# OUTPUT VARIABLES:
#   - RuntimeDefaults: Resolved project, log, and state paths.
#
# Copyright 2026 Douglas WF Acheson (dwfa@dwfa.ca)
# Licensed under Apache License 2.0. See LICENSE.md for details.
#
# Version: 1.0
# Date: July 05, 2026
##############################################################################

"""Default runtime paths for logs and state."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class RuntimeDefaults:
    """Resolved project-local runtime paths.

    Args:
        projectRoot: Resolved project root.
        logDir: Default directory for runtime logs.
        stateDir: Default directory for state files.
    """

    projectRoot: Path
    logDir: Path
    stateDir: Path

    @classmethod
    def forProject(cls, projectRoot: str | Path) -> "RuntimeDefaults":
        """Resolve runtime defaults for a project root.

        Args:
            projectRoot: Project root to resolve.

        Returns:
            Runtime defaults rooted under the given project.
        """

        root = Path(projectRoot).expanduser().resolve()
        return cls(
            projectRoot=root,
            logDir=root / "logs",
            stateDir=root / ".ansibleRunner" / "state",
        )
