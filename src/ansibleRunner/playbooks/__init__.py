##############################################################################
# Playbook domain helpers for ansibleRunner.
#
# USAGE:
#   from ansibleRunner.playbooks import discoverPlaybookEntries
#
# Copyright 2026 Douglas WF Acheson (dwfa@dwfa.ca)
# Licensed under Apache License 2.0. See LICENSE.md for details.
#
# Version: 1.0
# Date: July 11, 2026
##############################################################################

"""Playbook discovery, metadata, and configuration helpers."""

from ansibleRunner.playbooks.discovery import discoverPlaybookEntries, discoverPlaybooks
from ansibleRunner.playbooks.models import ConfigField, PlaybookConfig, PlaybookEntry
from ansibleRunner.playbooks.playbookConfig import (
    buildRunnerArgv,
    defaultPlaybookConfig,
    loadPlaybookConfigs,
    renderConfigSummary,
    savePlaybookConfigs,
)

__all__ = [
    "ConfigField",
    "PlaybookConfig",
    "PlaybookEntry",
    "buildRunnerArgv",
    "defaultPlaybookConfig",
    "discoverPlaybookEntries",
    "discoverPlaybooks",
    "loadPlaybookConfigs",
    "renderConfigSummary",
    "savePlaybookConfigs",
]
