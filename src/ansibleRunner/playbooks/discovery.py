##############################################################################
# Playbook discovery helpers.
#
# USAGE:
#   discoverPlaybookEntries(pbPath, configs)
#
# Copyright 2026 Douglas WF Acheson (dwfa@dwfa.ca)
# Licensed under Apache License 2.0. See LICENSE.md for details.
#
# Version: 1.0
# Date: July 11, 2026
##############################################################################

"""Playbook discovery helpers."""

from __future__ import annotations

import re
from pathlib import Path

from ansibleRunner.playbooks.metadata import parseTitle
from ansibleRunner.playbooks.models import PlaybookConfig, PlaybookEntry
from ansibleRunner.playbooks.playbookConfig import renderConfigSummary


TOP_LEVEL_LIST_ITEM_PATTERN = re.compile(r"^-\s+(?P<key>[\w.]+)\s*:")
PLAY_KEY_PATTERN = re.compile(r"^\s{2}(?P<key>[\w.]+)\s*:")
PLAY_KEYS = {"hosts", "import_playbook", "ansible.builtin.import_playbook"}


def discoverPlaybooks(playbookDir: Path) -> list[Path]:
    """Discover direct child playbook files.

    Args:
        playbookDir: Directory containing playbook YAML files.

    Returns:
        Sorted direct child ``*.yaml`` and ``*.yml`` playbook paths. Nested
        directories are intentionally ignored by this helper.
    """

    if not playbookDir.is_dir():
        return []
    return sorted(
        [
            path
            for path in playbookDir.iterdir()
            if path.is_file()
            and path.suffix.lower() in {".yaml", ".yml"}
            and isAnsiblePlaybook(path)
        ]
    )


def isAnsiblePlaybook(path: Path) -> bool:
    """Return whether a YAML file has an Ansible playbook document shape."""

    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeDecodeError):
        return False
    currentKeys: set[str] = set()
    sawListItem = False
    for rawLine in lines:
        line = rawLine.rstrip()
        strippedLine = line.strip()
        if (
            not strippedLine
            or strippedLine.startswith("---")
            or strippedLine.startswith("...")
            or strippedLine.startswith("#")
        ):
            continue
        listMatch = TOP_LEVEL_LIST_ITEM_PATTERN.match(line)
        if listMatch:
            if currentKeys & PLAY_KEYS:
                return True
            sawListItem = True
            currentKeys = {listMatch.group("key")}
            continue
        if not sawListItem:
            return False
        keyMatch = PLAY_KEY_PATTERN.match(line)
        if keyMatch:
            currentKeys.add(keyMatch.group("key"))
    return bool(currentKeys & PLAY_KEYS)


def discoverPlaybookDirectories(playbookDir: Path) -> list[Path]:
    """Discover direct child playbook grouping directories.

    Args:
        playbookDir: Directory containing playbooks and grouping directories.

    Returns:
        Sorted direct child directories that contain runnable playbooks,
        excluding hidden directories.
    """

    if not playbookDir.is_dir():
        return []
    return sorted(
        [
            path
            for path in playbookDir.iterdir()
            if path.is_dir()
            and not path.name.startswith(".")
            and directoryContainsPlaybook(path)
        ]
    )


def directoryContainsPlaybook(directory: Path) -> bool:
    """Return whether a directory tree contains any runnable playbook."""

    if not directory.is_dir():
        return False
    for path in directory.rglob("*"):
        if any(part.startswith(".") for part in path.relative_to(directory).parts):
            continue
        if (
            path.is_file()
            and path.suffix.lower() in {".yaml", ".yml"}
            and isAnsiblePlaybook(path)
        ):
            return True
    return False


def discoverPlaybookEntries(
    playbookDir: Path,
    configs: dict[str, PlaybookConfig] | None = None,
    currentDir: Path | None = None,
) -> list[PlaybookEntry]:
    """Discover playbooks with display metadata.

    Args:
        playbookDir: Root directory containing playbook YAML files.
        configs: Optional per-playbook configuration keyed by playbook stem.
        currentDir: Optional directory under ``playbookDir`` to list.

    Returns:
        Playbook entries suitable for display in a menu.
    """

    playbookConfigs = configs or {}
    activeDir = (currentDir or playbookDir).expanduser().resolve()
    rootDir = playbookDir.expanduser().resolve()
    entries: list[PlaybookEntry] = []

    if activeDir != rootDir and rootDir in activeDir.parents:
        entries.append(
            PlaybookEntry(
                configSummary="",
                displayName="..",
                name="..",
                path=activeDir.parent,
                title="Back",
                isDirectory=True,
            )
        )

    entries.extend(
        PlaybookEntry(
            configSummary="",
            displayName=f"📁 {path.name}",
            name=directoryConfigKey(rootDir, path),
            path=path,
            title="Directory",
            isDirectory=True,
        )
        for path in discoverPlaybookDirectories(activeDir)
    )

    entries.extend(
        PlaybookEntry(
            configSummary=renderConfigSummary(
                playbookConfigs.get(playbookConfigKey(rootDir, path))
            ),
            displayName=displayPlaybookName(path),
            name=playbookConfigKey(rootDir, path),
            path=path,
            title=parseTitle(path),
        )
        for path in discoverPlaybooks(activeDir)
    )
    return entries


def directoryConfigKey(rootDir: Path, path: Path) -> str:
    """Return a stable key for a playbook directory entry."""

    return str(path.relative_to(rootDir))


def playbookConfigKey(rootDir: Path, path: Path) -> str:
    """Return a path-aware playbook config key.

    Args:
        rootDir: Root playbook directory.
        path: Playbook path.

    Returns:
        Relative playbook path without the file suffix.
    """

    relativePath = path.relative_to(rootDir)
    return str(relativePath.with_suffix(""))


def displayPlaybookName(path: Path) -> str:
    """Return a compact display name for a playbook.

    Args:
        path: Playbook path to format.

    Returns:
        Playbook stem with the conventional trailing ``-pb`` suffix removed.
    """

    name = path.stem
    if name.endswith("-pb"):
        return name[:-3]
    return name
