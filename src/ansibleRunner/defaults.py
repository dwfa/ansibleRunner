##############################################################################
# Default runtime paths for ansibleRunner logs, state, and playbooks.
#
# USAGE:
#   RuntimeDefaults.forArPath(arPath, pbPath)
#
# OUTPUT VARIABLES:
#   - RuntimeDefaults: Resolved runner, playbook, log, and state paths.
#
# Copyright 2026 Douglas WF Acheson (dwfa@dwfa.ca)
# Licensed under Apache License 2.0. See LICENSE.md for details.
#
# Version: 1.0
# Date: July 05, 2026
##############################################################################

"""Default runtime paths for logs, state, and playbook discovery."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class RuntimeDefaults:
    """Resolved ansibleRunner runtime paths.

    Args:
        arPath: Directory that anchors runtime state, logs, and command cwd.
        pbPath: Directory that anchors playbook discovery.
        logDir: Directory for runtime logs.
        stateDir: Directory for state files.
    """

    arPath: Path
    pbPath: Path
    logDir: Path
    stateDir: Path

    @classmethod
    def forArPath(
        cls,
        arPath: str | Path,
        pbPath: str | Path | None = None,
    ) -> "RuntimeDefaults":
        """Resolve runtime defaults for an ansibleRunner anchor path.

        Args:
            arPath: Directory that owns logs, state, and runner cwd.
            pbPath: Optional playbook root. Defaults to ``arPath/playbooks``.

        Returns:
            Runtime defaults rooted under the given ansibleRunner path.
        """

        runnerPath = Path(arPath).expanduser().resolve()
        playbookPath = (
            Path(pbPath).expanduser().resolve()
            if pbPath is not None
            else runnerPath / "playbooks"
        )
        return cls(
            arPath=runnerPath,
            pbPath=playbookPath,
            logDir=runnerPath / "logs",
            stateDir=runnerPath / ".ansibleRunner" / "state",
        )
