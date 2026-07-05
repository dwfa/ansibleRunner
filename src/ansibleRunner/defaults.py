"""Default runtime paths for logs and state."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class RuntimeDefaults:
    project_root: Path
    log_dir: Path
    state_dir: Path

    @classmethod
    def for_project(cls, project_root: Path) -> "RuntimeDefaults":
        root = project_root.expanduser().resolve()
        return cls(
            project_root=root,
            log_dir=root / ".ansibleRunner" / "logs",
            state_dir=root / ".ansibleRunner" / "state",
        )

