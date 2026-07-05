"""Application and menu orchestration."""

from __future__ import annotations

import argparse
from collections.abc import Sequence
from pathlib import Path

from ansibleRunner.defaults import RuntimeDefaults


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="ansibleRunner",
        description="Run project-local Ansible management workflows.",
    )
    parser.add_argument(
        "--project-root",
        type=Path,
        default=None,
        help="Project root containing playbooks, logs, and state.",
    )
    parser.add_argument(
        "--list-defaults",
        action="store_true",
        help="Print resolved log and state defaults, then exit.",
    )
    return parser


class AnsibleRunnerApp:
    """Coordinates menu flow and command execution for a project root."""

    def __init__(self, project_root: Path, defaults: RuntimeDefaults | None = None) -> None:
        self.project_root = project_root.expanduser().resolve()
        self.defaults = defaults or RuntimeDefaults.for_project(self.project_root)

    def run(self, argv: Sequence[str] | None = None) -> int:
        parser = build_parser()
        args = parser.parse_args(list(argv or ()))

        if args.project_root is not None:
            self.project_root = args.project_root.expanduser().resolve()
            self.defaults = RuntimeDefaults.for_project(self.project_root)

        if args.list_defaults:
            self._print_defaults()
            return 0

        self._print_defaults()
        return 0

    def _print_defaults(self) -> None:
        print(f"project_root={self.project_root}")
        print(f"log_dir={self.defaults.log_dir}")
        print(f"state_dir={self.defaults.state_dir}")


def main(project_root: str | Path, argv: Sequence[str] | None = None) -> int:
    """Run ansibleRunner for a project.

    This is the stable handoff point for project-specific wrappers such as
    `rpiMgmt`. Wrappers should resolve their own project root and pass it here.
    """

    app = AnsibleRunnerApp(Path(project_root))
    return app.run(argv)

