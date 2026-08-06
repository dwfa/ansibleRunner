##############################################################################
# Playbook discovery helpers.
#
# USAGE:
#   discoverPlaybookEntries(projectRoot / "playbooks", configs)
#
# Copyright 2026 Douglas WF Acheson (dwfa@dwfa.ca)
# Licensed under Apache License 2.0. See LICENSE.md for details.
#
# Version: 1.0
# Date: July 11, 2026
##############################################################################

"""Playbook discovery helpers."""

from __future__ import annotations

from pathlib import Path

from ansibleRunner.playbooks.metadata import parseTitle
from ansibleRunner.playbooks.models import PlaybookConfig, PlaybookEntry
from ansibleRunner.playbooks.playbookConfig import renderConfigSummary


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
            if path.is_file() and path.suffix in {".yaml", ".yml"}
        ]
    )


def discoverPlaybookDirectories(playbookDir: Path) -> list[Path]:
    """Discover direct child playbook grouping directories.

    Args:
        playbookDir: Directory containing playbooks and grouping directories.

    Returns:
        Sorted direct child directories, excluding hidden directories.
    """

    if not playbookDir.is_dir():
        return []
    return sorted(
        [
            path
            for path in playbookDir.iterdir()
            if path.is_dir() and not path.name.startswith(".")
        ]
    )


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
