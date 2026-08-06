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
    directoryConfigKey,
    discoverPlaybookEntries,
    discoverPlaybookDirectories,
    discoverPlaybooks,
    displayPlaybookName,
    playbookConfigKey,
)
from ansibleRunner.playbooks.models import PlaybookConfig


def testDiscoverPlaybooksReturnsTopLevelYamlOnly(tmp_path: Path) -> None:
    """Verify only direct child YAML playbooks are discovered."""

    playbookDir = tmp_path / "playbooks"
    nestedDir = playbookDir / "vars"
    nestedDir.mkdir(parents=True)
    sitePlaybook = playbookDir / "site.yaml"
    shortPlaybook = playbookDir / "short.yml"
    otherFile = playbookDir / "notes.txt"
    nestedPlaybook = nestedDir / "nested.yaml"
    sitePlaybook.write_text("---\n", encoding="utf-8")
    shortPlaybook.write_text("---\n", encoding="utf-8")
    otherFile.write_text("notes\n", encoding="utf-8")
    nestedPlaybook.write_text("---\n", encoding="utf-8")

    assert discoverPlaybooks(playbookDir) == [shortPlaybook, sitePlaybook]


def testDiscoverPlaybookDirectoriesReturnsVisibleDirectories(tmp_path: Path) -> None:
    """Verify direct visible playbook grouping directories are discovered."""

    playbookDir = tmp_path / "playbooks"
    dbDir = playbookDir / "db"
    hiddenDir = playbookDir / ".hidden"
    dbDir.mkdir(parents=True)
    hiddenDir.mkdir()

    assert discoverPlaybookDirectories(playbookDir) == [dbDir]


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


def testDiscoverPlaybookEntriesShowsDirectoriesBeforePlaybooks(tmp_path: Path) -> None:
    """Verify menu entries show directories first and playbooks second."""

    playbookDir = tmp_path / "playbooks"
    dbDir = playbookDir / "db"
    dbDir.mkdir(parents=True)
    playbook = playbookDir / "site.yaml"
    playbook.write_text("# Site\n---\n", encoding="utf-8")

    entries = discoverPlaybookEntries(playbookDir)

    assert [entry.displayName for entry in entries] == ["📁 db", "site"]
    assert entries[0].isDirectory is True
    assert entries[1].isDirectory is False


def testDiscoverPlaybookEntriesCanListNestedDirectory(tmp_path: Path) -> None:
    """Verify nested directories include a parent row and path-aware config keys."""

    playbookDir = tmp_path / "playbooks"
    dbDir = playbookDir / "db"
    dbDir.mkdir(parents=True)
    playbook = dbDir / "listServers-pb.yaml"
    playbook.write_text("# List DB servers\n---\n", encoding="utf-8")

    entries = discoverPlaybookEntries(
        playbookDir,
        {"db/listServers-pb": PlaybookConfig(node="db")},
        dbDir,
    )

    assert [entry.displayName for entry in entries] == ["..", "listServers"]
    assert entries[0].isDirectory is True
    assert entries[0].path == playbookDir
    assert entries[1].name == "db/listServers-pb"
    assert entries[1].configSummary == "-n db"


def testPlaybookConfigKeysArePathAware(tmp_path: Path) -> None:
    """Verify config keys include grouping directories for nested playbooks."""

    playbookDir = tmp_path / "playbooks"
    dbDir = playbookDir / "db"
    dbDir.mkdir(parents=True)

    assert directoryConfigKey(playbookDir, dbDir) == "db"
    assert playbookConfigKey(playbookDir, dbDir / "list-pb.yaml") == "db/list-pb"


def testDisplayPlaybookNameRemovesTrailingPbSuffix(tmp_path: Path) -> None:
    """Verify display names trim the conventional playbook suffix."""

    assert displayPlaybookName(tmp_path / "buildDNSServer-pb.yaml") == "buildDNSServer"


def testDisplayPlaybookNamePreservesOtherNames(tmp_path: Path) -> None:
    """Verify display names preserve non-conventional names."""

    assert displayPlaybookName(tmp_path / "site.yaml") == "site"
