"""Subprocess-backed Ansible command runner."""

from __future__ import annotations

import subprocess
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from ansibleRunner.progress import RunProgress


@dataclass(frozen=True)
class RunnerResult:
    command: tuple[str, ...]
    return_code: int
    stdout: str
    stderr: str

    @property
    def progress(self) -> RunProgress:
        return RunProgress.finished(self.return_code)


class AnsibleCommandRunner:
    """Runs Ansible commands from a project root."""

    def __init__(self, project_root: Path) -> None:
        self.project_root = project_root.expanduser().resolve()

    def run(self, command: Sequence[str]) -> RunnerResult:
        completed = subprocess.run(
            list(command),
            cwd=self.project_root,
            check=False,
            text=True,
            capture_output=True,
        )
        return RunnerResult(
            command=tuple(command),
            return_code=completed.returncode,
            stdout=completed.stdout,
            stderr=completed.stderr,
        )

