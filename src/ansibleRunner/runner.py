##############################################################################
# Subprocess-backed Ansible command runner.
#
# USAGE:
#   AnsibleCommandRunner(projectRoot).run(["ansible-playbook", "site.yml"])
#
# OUTPUT VARIABLES:
#   - RunnerResult: Captured command result and derived progress snapshot.
#
# Copyright 2026 Douglas WF Acheson (dwfa@dwfa.ca)
# Licensed under Apache License 2.0. See LICENSE.md for details.
#
# Version: 1.0
# Date: July 05, 2026
##############################################################################

"""Subprocess-backed Ansible command runner."""

from __future__ import annotations

import subprocess
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from ansibleRunner.progress import RunProgress


@dataclass(frozen=True)
class RunnerResult:
    """Captured result from an Ansible subprocess command.

    Args:
        command: Command and arguments that were executed.
        returnCode: Process return code.
        stdout: Captured standard output.
        stderr: Captured standard error.
    """

    command: tuple[str, ...]
    returnCode: int
    stdout: str
    stderr: str

    @property
    def progress(self) -> RunProgress:
        """Return the progress state derived from the process return code.

        Returns:
            Finished progress snapshot.
        """

        return RunProgress.finished(self.returnCode)


class AnsibleCommandRunner:
    """Runs Ansible commands from a project root."""

    def __init__(self, projectRoot: Path) -> None:
        """Initialize a subprocess runner for a project root.

        Args:
            projectRoot: Directory where commands should be executed.
        """

        self.projectRoot = projectRoot.expanduser().resolve()

    def run(self, command: Sequence[str]) -> RunnerResult:
        """Run a command in the configured project root.

        Args:
            command: Command and arguments to execute.

        Returns:
            Captured command result.
        """

        completed = subprocess.run(
            list(command),
            cwd=self.projectRoot,
            check=False,
            text=True,
            capture_output=True,
        )
        return RunnerResult(
            command=tuple(command),
            returnCode=completed.returncode,
            stdout=completed.stdout,
            stderr=completed.stderr,
        )
