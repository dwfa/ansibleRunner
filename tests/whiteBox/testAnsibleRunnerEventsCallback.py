##############################################################################
# White-box tests for ansibleRunner event callback helpers.
#
# USAGE:
#   python3 -m pytest tests/whiteBox/testAnsibleRunnerEventsCallback.py
#
# WORKFLOW:
#   1. Verify callback helper extraction works without a live Ansible process.
#
# Copyright 2026 Douglas WF Acheson (dwfa@dwfa.ca)
# Licensed under Apache License 2.0. See LICENSE.md for details.
#
# Version: 1.0
# Date: August 02, 2026
##############################################################################

from __future__ import annotations

from typing import Any

from ansibleRunner.ansible_callbacks.ansible_runner_events import CallbackModule


class NamedObject:
    """Small object with Ansible-like get_name behavior."""

    def __init__(self, name: str) -> None:
        """Initialize test object."""

        self.name = name

    def get_name(self) -> str:
        """Return the configured object name."""

        return self.name


class TaskObject(NamedObject):
    """Small object with Ansible-like task behavior."""

    action = "copy"

    def get_path(self) -> str:
        """Return an Ansible-like task path."""

        return "/tmp/task.yaml:12"


def testCallbackExtractsIncludeHostsFromList() -> None:
    """Verify include host metadata accepts Ansible list-shaped values."""

    callback = CallbackModule()
    includedFile = type(
        "IncludedFile",
        (),
        {
            "_filename": "/tmp/include.yaml",
            "_hosts": [NamedObject("web"), NamedObject("db")],
            "_task": TaskObject("include task"),
        },
    )()

    include = callback._include(includedFile)

    assert include["filename"] == "/tmp/include.yaml"
    assert include["hosts"] == ["db", "web"]
    assert include["task"]["action"] == "copy"
    assert include["task"]["name"] == "include task"
    assert include["task"]["path"] == "/tmp/task.yaml:12"


def testCallbackExtractsIncludeHostsFromDict() -> None:
    """Verify include host metadata accepts Ansible dict-shaped values."""

    callback = CallbackModule()

    assert callback._hosts({"web": object(), "db": object()}) == ["db", "web"]


def testCallbackExtractsResultTaskDetails() -> None:
    """Verify result events include host, task, and result details."""

    callback = CallbackModule()
    result = type(
        "Result",
        (),
        {
            "_host": NamedObject("installer"),
            "_task": TaskObject("copy image"),
            "_result": {
                "changed": True,
                "item": "image",
                "msg": "done",
                "rc": 0,
            },
        },
    )()

    eventResult: dict[str, Any] = callback._result(result)

    assert eventResult["changed"] is True
    assert eventResult["host"] == "installer"
    assert eventResult["item"] == "image"
    assert eventResult["msg"] == "done"
    assert eventResult["rc"] == 0
    assert eventResult["task"]["action"] == "copy"
