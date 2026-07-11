##############################################################################
# Editable playbook configuration field definitions.
#
# USAGE:
#   CONFIG_FIELDS
#
# Copyright 2026 Douglas WF Acheson (dwfa@dwfa.ca)
# Licensed under Apache License 2.0. See LICENSE.md for details.
#
# Version: 1.0
# Date: July 11, 2026
##############################################################################

"""Editable playbook configuration fields."""

from __future__ import annotations

from ansibleRunner.playbooks.models import ConfigField


OUTPUT_LEVELS: tuple[str, ...] = ("play", "role", "task")

CONFIG_FIELDS: tuple[ConfigField, ...] = (
    ConfigField(key="node", label="Node", kind="string"),
    ConfigField(
        choices=OUTPUT_LEVELS,
        key="outputLevel",
        kind="choice",
        label="Output level",
    ),
    ConfigField(key="debug", label="Debug        (-d)", kind="bool"),
    ConfigField(key="check", label="Check        (-c)", kind="bool"),
    ConfigField(key="syntaxCheck", label="Syntax check (-s)", kind="bool"),
    ConfigField(key="listTasks", label="List tasks   (-t)", kind="bool"),
)

LAUNCH_CONFIG_FIELDS: tuple[ConfigField, ...] = (
    *CONFIG_FIELDS,
    ConfigField(key="extraArgs", label="Ansible arguments", kind="args"),
)
