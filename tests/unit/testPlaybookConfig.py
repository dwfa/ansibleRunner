##############################################################################
# Playbook configuration unit tests for ansibleRunner.
#
# USAGE:
#   python3 -m pytest tests/unit/testPlaybookConfig.py
#
# WORKFLOW:
#   1. Verify playbook config defaults and summaries.
#   2. Verify config load/save behavior.
#   3. Verify runner argument generation.
#
# Copyright 2026 Douglas WF Acheson (dwfa@dwfa.ca)
# Licensed under Apache License 2.0. See LICENSE.md for details.
#
# Version: 1.0
# Date: July 11, 2026
##############################################################################

from __future__ import annotations

from pathlib import Path

from ansibleRunner.playbooks.models import PlaybookConfig
from ansibleRunner.playbooks.playbookConfig import (
    buildRunnerArgv,
    defaultPlaybookConfig,
    loadPlaybookConfigs,
    renderConfigSummary,
    savePlaybookConfigs,
)


def testDefaultPlaybookConfigMatchesRunnerDefaults() -> None:
    """Verify playbook config defaults match expected runner defaults."""

    config = defaultPlaybookConfig()

    assert config == PlaybookConfig()
    assert config.outputLevel == "role"
    assert config.node == ""


def testRenderConfigSummaryReturnsUnsetForDefaults() -> None:
    """Verify default config displays as unset."""

    assert renderConfigSummary(defaultPlaybookConfig()) == "(unset)"


def testRenderConfigSummaryIncludesEnabledFlags() -> None:
    """Verify enabled config values are rendered compactly."""

    config = PlaybookConfig(
        check=True,
        debug=True,
        extraArgs=("--limit", "one"),
        listTasks=True,
        node="dns",
        outputLevel="task",
        syntaxCheck=True,
    )

    assert renderConfigSummary(config) == (
        "-d -c -s -t -n dns --output-level task --limit one"
    )


def testBuildRunnerArgvTranslatesConfig() -> None:
    """Verify playbook config translates to runner arguments."""

    config = PlaybookConfig(
        check=True,
        debug=True,
        extraArgs=("--limit", "one"),
        listTasks=True,
        node="dns",
        outputLevel="task",
        syntaxCheck=True,
    )

    assert buildRunnerArgv(config) == [
        "-d",
        "-c",
        "-s",
        "-t",
        "-n",
        "dns",
        "--output-level",
        "task",
        "--limit",
        "one",
    ]


def testLoadPlaybookConfigsReturnsEmptyForMissingFile(tmp_path: Path) -> None:
    """Verify missing config files produce empty config maps."""

    assert loadPlaybookConfigs(tmp_path / "missing.json") == {}


def testLoadPlaybookConfigsReturnsEmptyForMalformedFile(tmp_path: Path) -> None:
    """Verify malformed config files are ignored safely."""

    configPath = tmp_path / "playbookConfig.json"
    configPath.write_text("{not json\n", encoding="utf-8")

    assert loadPlaybookConfigs(configPath) == {}


def testSaveAndLoadPlaybookConfigsRoundTrip(tmp_path: Path) -> None:
    """Verify playbook configs persist and load correctly."""

    configPath = tmp_path / "state" / "playbookConfig.json"
    configs = {
        "site": PlaybookConfig(
            check=True,
            extraArgs=("--tags", "dns"),
            node="dns",
            outputLevel="play",
        )
    }

    savePlaybookConfigs(configPath, configs)

    assert loadPlaybookConfigs(configPath) == configs
