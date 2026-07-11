##############################################################################
# TUI routing black-box tests for ansibleRunner.
#
# USAGE:
#   python3 -m pytest tests/blackBox/testTuiRouting.py
#
# WORKFLOW:
#   1. Verify no-flag app startup launches the TUI path.
#
# Copyright 2026 Douglas WF Acheson (dwfa@dwfa.ca)
# Licensed under Apache License 2.0. See LICENSE.md for details.
#
# Version: 1.0
# Date: July 11, 2026
##############################################################################

from __future__ import annotations

from pathlib import Path
from typing import Any

from ansibleRunner.app import AnsibleRunnerApp


def testAppLaunchesTuiWhenNoDiagnosticFlag(
    monkeypatch: Any,
    tmp_path: Path,
) -> None:
    """Verify the default app path launches the TUI."""

    calls: list[Path] = []

    def fakeRunTui(defaults: Any) -> int:
        """Capture TUI launch defaults."""

        calls.append(defaults.projectRoot)
        return 0

    monkeypatch.setattr("ansibleRunner.app.runTui", fakeRunTui)

    result = AnsibleRunnerApp(tmp_path).run([])

    assert result == 0
    assert calls == [tmp_path.resolve()]
