"""Command-line entrypoint."""

from __future__ import annotations

import sys
from pathlib import Path

from ansibleRunner.app import main as run_app


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    project_root = Path.cwd()
    return run_app(project_root, args)

