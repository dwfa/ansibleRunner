##############################################################################
# Helpers for reading past runner event logs from the TUI.
#
# USAGE:
#   from ansibleRunner.tui.runLogs import lastRunHostForPlaybook
#   host = lastRunHostForPlaybook(defaults.logDir, entry.path)
#
# Copyright 2026 Douglas WF Acheson (dwfa@dwfa.ca)
# Licensed under Apache License 2.0. See LICENSE.md for details.
#
# Version: 1.0
# Date: October 14, 2026
##############################################################################

"""TUI helpers for identifying the effective target host of a run."""

from __future__ import annotations

from typing import Mapping


# Role names that run on the local controller as part of the standard
# bootstrap/cleanup wrapper plays. Events emitted under these roles do
# NOT identify the real playbook target and should be ignored when
# resolving the current run's host for the title bar.
#
# TODO: when a second downstream project needs a different set, promote
# this to a project config key (e.g. .ansibleRunner/config.json
# initRoles: [...]) rather than editing the package.
INIT_ROLE_NAMES: frozenset[str] = frozenset({
    "bootstrap",
    "writeSSHKey",
    "prepareRemoteCredentials",
    "clearLocal",
})


def isInitRoleEvent(event: Mapping[str, object]) -> bool:
    """Return True when a runner event belongs to an init/cleanup role.

    Args:
        event: Parsed runner event dict with the usual callback shape.

    Returns:
        True when the event's task role is in INIT_ROLE_NAMES.
    """

    task = _taskField(event)
    role = task.get("role") if isinstance(task, dict) else None
    return isinstance(role, str) and role in INIT_ROLE_NAMES


def hostFromEvent(event: Mapping[str, object]) -> str | None:
    """Return the target host from a runner event, or None.

    Returns the ``result.host`` value when the event is a per-host
    result (``runner_ok`` / ``runner_failed`` / ``runner_item_ok``),
    excluding events from init/cleanup roles. ``localhost`` is a
    legitimate target for playbooks that do all their work on the
    controller, so it is NOT filtered.

    Args:
        event: Parsed runner event dict.

    Returns:
        Target hostname, or None when the event does not identify one.
    """

    if isInitRoleEvent(event):
        return None
    result = event.get("result")
    if not isinstance(result, dict):
        return None
    host = result.get("host")
    if not isinstance(host, str) or not host:
        return None
    return host


def _taskField(event: Mapping[str, object]) -> Mapping[str, object] | None:
    """Return the task dict from a runner event, if present."""

    task = event.get("task")
    if isinstance(task, dict):
        return task
    result = event.get("result")
    if isinstance(result, dict):
        innerTask = result.get("task")
        if isinstance(innerTask, dict):
            return innerTask
    return None
