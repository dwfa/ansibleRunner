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
    """Discover top-level playbook files.

    Args:
        playbookDir: Directory containing playbook YAML files.

    Returns:
        Sorted top-level ``*.yaml`` playbook paths. Nested directories are
        intentionally ignored.
    """

    if not playbookDir.is_dir():
        return []
    return sorted(playbookDir.glob("*.yaml"))


def discoverPlaybookEntries(
    playbookDir: Path,
    configs: dict[str, PlaybookConfig] | None = None,
) -> list[PlaybookEntry]:
    """Discover playbooks with display metadata.

    Args:
        playbookDir: Directory containing playbook YAML files.
        configs: Optional per-playbook configuration keyed by playbook stem.

    Returns:
        Playbook entries suitable for display in a menu.
    """

    playbookConfigs = configs or {}
    return [
        PlaybookEntry(
            configSummary=renderConfigSummary(playbookConfigs.get(path.stem)),
            displayName=displayPlaybookName(path),
            name=path.stem,
            path=path,
            title=parseTitle(path),
        )
        for path in discoverPlaybooks(playbookDir)
    ]


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
