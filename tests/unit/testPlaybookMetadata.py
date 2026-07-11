##############################################################################
# Playbook metadata unit tests for ansibleRunner.
#
# USAGE:
#   python3 -m pytest tests/unit/testPlaybookMetadata.py
#
# WORKFLOW:
#   1. Verify playbook title parsing.
#   2. Verify title fallback behavior.
#
# Copyright 2026 Douglas WF Acheson (dwfa@dwfa.ca)
# Licensed under Apache License 2.0. See LICENSE.md for details.
#
# Version: 1.0
# Date: July 11, 2026
##############################################################################

from __future__ import annotations

from pathlib import Path

from ansibleRunner.playbooks.metadata import parseTitle


def testParseTitleUsesFirstMeaningfulHeaderComment(tmp_path: Path) -> None:
    """Verify title parsing skips dividers and blank comments."""

    playbook = tmp_path / "site.yaml"
    playbook.write_text(
        "##############################################################################\n"
        "#\n"
        "# Configure DNS services\n"
        "# More detail ignored\n"
        "---\n",
        encoding="utf-8",
    )

    assert parseTitle(playbook) == "Configure DNS services"


def testParseTitleReturnsNoTitleWhenMissing(tmp_path: Path) -> None:
    """Verify missing title comments produce a fallback marker."""

    playbook = tmp_path / "site.yaml"
    playbook.write_text("---\n", encoding="utf-8")

    assert parseTitle(playbook) == "(no title)"


def testParseTitleReturnsUnreadableForMissingFile(tmp_path: Path) -> None:
    """Verify unreadable playbooks produce a fallback marker."""

    assert parseTitle(tmp_path / "missing.yaml") == "(unreadable)"
