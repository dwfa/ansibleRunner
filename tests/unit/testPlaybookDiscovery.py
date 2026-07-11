##############################################################################
# Playbook discovery unit tests for ansibleRunner.
#
# USAGE:
#   python3 -m pytest tests/unit/testPlaybookDiscovery.py
#
# WORKFLOW:
#   1. Verify top-level playbook discovery.
#   2. Verify playbook entry construction.
#
# Copyright 2026 Douglas WF Acheson (dwfa@dwfa.ca)
# Licensed under Apache License 2.0. See LICENSE.md for details.
#
# Version: 1.0
# Date: July 11, 2026
##############################################################################

from __future__ import annotations

from pathlib import Path

from ansibleRunner.playbooks.discovery import (
    discoverPlaybookEntries,
    discoverPlaybooks,
    displayPlaybookName,
)
from ansibleRunner.playbooks.models import PlaybookConfig


def testDiscoverPlaybooksReturnsTopLevelYamlOnly(tmp_path: Path) -> None:
    """Verify only top-level YAML playbooks are discovered."""

    playbookDir = tmp_path / "playbooks"
    nestedDir = playbookDir / "vars"
    nestedDir.mkdir(parents=True)
    sitePlaybook = playbookDir / "site.yaml"
    otherFile = playbookDir / "notes.txt"
    nestedPlaybook = nestedDir / "nested.yaml"
    sitePlaybook.write_text("---\n", encoding="utf-8")
    otherFile.write_text("notes\n", encoding="utf-8")
    nestedPlaybook.write_text("---\n", encoding="utf-8")

    assert discoverPlaybooks(playbookDir) == [sitePlaybook]


def testDiscoverPlaybooksReturnsEmptyForMissingDirectory(tmp_path: Path) -> None:
    """Verify missing playbook directories are handled gracefully."""

    assert discoverPlaybooks(tmp_path / "missing") == []


def testDiscoverPlaybookEntriesIncludeTitleAndConfig(tmp_path: Path) -> None:
    """Verify playbook entries include metadata and config summaries."""

    playbookDir = tmp_path / "playbooks"
    playbookDir.mkdir()
    playbook = playbookDir / "site.yaml"
    playbook.write_text(
        "##############################################################################\n"
        "# Configure DNS services\n"
        "##############################################################################\n"
        "---\n",
        encoding="utf-8",
    )

    entries = discoverPlaybookEntries(
        playbookDir,
        {"site": PlaybookConfig(check=True, node="dns")},
    )

    assert len(entries) == 1
    assert entries[0].name == "site"
    assert entries[0].displayName == "site"
    assert entries[0].path == playbook
    assert entries[0].title == "Configure DNS services"
    assert entries[0].configSummary == "-c -n dns"


def testDisplayPlaybookNameRemovesTrailingPbSuffix(tmp_path: Path) -> None:
    """Verify display names trim the conventional playbook suffix."""

    assert displayPlaybookName(tmp_path / "buildDNSServer-pb.yaml") == "buildDNSServer"


def testDisplayPlaybookNamePreservesOtherNames(tmp_path: Path) -> None:
    """Verify display names preserve non-conventional names."""

    assert displayPlaybookName(tmp_path / "site.yaml") == "site"
