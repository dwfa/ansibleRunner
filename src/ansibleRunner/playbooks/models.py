##############################################################################
# Playbook domain models for ansibleRunner.
#
# USAGE:
#   PlaybookEntry(...)
#
# Copyright 2026 Douglas WF Acheson (dwfa@dwfa.ca)
# Licensed under Apache License 2.0. See LICENSE.md for details.
#
# Version: 1.0
# Date: July 11, 2026
##############################################################################

"""Playbook domain models."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class ConfigField:
    """Editable playbook configuration field.

    Args:
        key: Storage key in a playbook configuration.
        label: Human-readable field label.
        kind: Field kind such as ``bool``, ``choice``, ``string``, or ``args``.
        choices: Optional valid values for choice fields.
    """

    key: str
    label: str
    kind: str
    choices: tuple[str, ...] = ()


@dataclass(frozen=True)
class PlaybookConfig:
    """Persisted or per-run playbook configuration.

    Args:
        check: Whether to run Ansible in check mode.
        debug: Whether to pass ``debugFlag=1``.
        extraArgs: Launch-only extra Ansible arguments.
        listTasks: Whether to pass ``--list-tasks``.
        node: Optional Ansible node/group.
        outputLevel: Progress detail level.
        syntaxCheck: Whether to pass ``--syntax-check``.
    """

    check: bool = False
    debug: bool = False
    extraArgs: tuple[str, ...] = field(default_factory=tuple)
    listTasks: bool = False
    node: str = ""
    outputLevel: str = "role"
    syntaxCheck: bool = False


@dataclass(frozen=True)
class PlaybookEntry:
    """Discovered playbook display entry.

    Args:
        configSummary: Compact display summary of the playbook config.
        displayName: Compact playbook name for display.
        name: Playbook stem used as the config key.
        path: Filesystem path to the playbook.
        title: Display title parsed from the playbook header.
        isDirectory: Whether this entry opens a playbook subdirectory.
    """

    configSummary: str
    displayName: str
    name: str
    path: Path
    title: str
    isDirectory: bool = False
