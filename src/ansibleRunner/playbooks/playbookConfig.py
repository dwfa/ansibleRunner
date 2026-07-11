##############################################################################
# Playbook configuration helpers.
#
# USAGE:
#   loadPlaybookConfigs(path)
#
# Copyright 2026 Douglas WF Acheson (dwfa@dwfa.ca)
# Licensed under Apache License 2.0. See LICENSE.md for details.
#
# Version: 1.0
# Date: July 11, 2026
##############################################################################

"""Playbook configuration helpers."""

from __future__ import annotations

import json
import shlex
from dataclasses import asdict
from pathlib import Path
from typing import Any

from ansibleRunner.playbooks.models import PlaybookConfig


def defaultPlaybookConfig() -> PlaybookConfig:
    """Return the default playbook configuration.

    Returns:
        Default playbook configuration.
    """

    return PlaybookConfig()


def playbookConfigFromMapping(values: dict[str, Any]) -> PlaybookConfig:
    """Build a playbook configuration from JSON-compatible values.

    Args:
        values: Raw mapping loaded from persistent storage.

    Returns:
        Normalized playbook configuration.
    """

    return PlaybookConfig(
        check=bool(values.get("check", False)),
        debug=bool(values.get("debug", False)),
        extraArgs=tuple(str(value) for value in values.get("extraArgs", ())),
        listTasks=bool(values.get("listTasks", False)),
        node=str(values.get("node", "") or ""),
        outputLevel=str(values.get("outputLevel", "role") or "role"),
        syntaxCheck=bool(values.get("syntaxCheck", False)),
    )


def playbookConfigToMapping(config: PlaybookConfig) -> dict[str, Any]:
    """Convert a playbook configuration to JSON-compatible values.

    Args:
        config: Playbook configuration to serialize.

    Returns:
        JSON-compatible mapping.
    """

    values = asdict(config)
    values["extraArgs"] = list(config.extraArgs)
    return values


def loadPlaybookConfigs(configPath: Path) -> dict[str, PlaybookConfig]:
    """Load per-playbook configuration from disk.

    Args:
        configPath: JSON file containing playbook configuration.

    Returns:
        Per-playbook configuration keyed by playbook name. Missing, malformed,
        or unreadable files produce an empty mapping.
    """

    if not configPath.exists():
        return {}

    try:
        rawConfigs = json.loads(configPath.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}

    if not isinstance(rawConfigs, dict):
        return {}

    configs: dict[str, PlaybookConfig] = {}
    for playbookName, rawConfig in rawConfigs.items():
        if isinstance(playbookName, str) and isinstance(rawConfig, dict):
            configs[playbookName] = playbookConfigFromMapping(rawConfig)
    return configs


def savePlaybookConfigs(
    configPath: Path,
    configs: dict[str, PlaybookConfig],
) -> None:
    """Save per-playbook configuration to disk.

    Args:
        configPath: JSON file that receives playbook configuration.
        configs: Per-playbook configuration keyed by playbook name.
    """

    configPath.parent.mkdir(parents=True, exist_ok=True)
    rawConfigs = {
        playbookName: playbookConfigToMapping(config)
        for playbookName, config in sorted(configs.items())
    }
    configPath.write_text(
        json.dumps(rawConfigs, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def renderConfigSummary(config: PlaybookConfig | None) -> str:
    """Render compact playbook configuration text.

    Args:
        config: Optional playbook configuration.

    Returns:
        Compact argument-style summary for display in playbook menus.
    """

    playbookConfig = config or defaultPlaybookConfig()
    parts: list[str] = []
    if playbookConfig.debug:
        parts.append("-d")
    if playbookConfig.check:
        parts.append("-c")
    if playbookConfig.syntaxCheck:
        parts.append("-s")
    if playbookConfig.listTasks:
        parts.append("-t")
    if playbookConfig.node:
        parts.append(f"-n {playbookConfig.node}")
    if playbookConfig.outputLevel != "role":
        parts.append(f"--output-level {playbookConfig.outputLevel}")
    if playbookConfig.extraArgs:
        parts.append(shlex.join(playbookConfig.extraArgs))
    return " ".join(parts) if parts else "(unset)"


def buildRunnerArgv(config: PlaybookConfig) -> list[str]:
    """Build runner arguments from playbook configuration.

    Args:
        config: Playbook configuration to translate.

    Returns:
        Runner argument list.
    """

    args: list[str] = []
    if config.debug:
        args.append("-d")
    if config.check:
        args.append("-c")
    if config.syntaxCheck:
        args.append("-s")
    if config.listTasks:
        args.append("-t")
    if config.node:
        args.extend(["-n", config.node])
    args.extend(["--output-level", config.outputLevel])
    args.extend(config.extraArgs)
    return args
