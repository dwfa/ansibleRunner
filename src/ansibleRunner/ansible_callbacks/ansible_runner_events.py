##############################################################################
# Ansible callback plugin for runner event inspection.
#
# USAGE:
#   ANSIBLE_CALLBACK_PLUGINS=/path/to/ansible_callbacks
#   ANSIBLE_CALLBACKS_ENABLED=ansible_runner_events
#   ANSIBLE_RUNNER_EVENT_LOG=/path/to/run.events.jsonl
#
# OUTPUT VARIABLES:
#   - JSON Lines event stream at ANSIBLE_RUNNER_EVENT_LOG.
#
# Copyright 2026 Douglas WF Acheson (dwfa@dwfa.ca)
# Licensed under Apache License 2.0. See LICENSE.md for details.
#
# Version: 1.0
# Date: August 02, 2026
##############################################################################

"""Ansible callback plugin that records structured lifecycle events."""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    from ansible.plugins.callback import CallbackBase
except ImportError:
    class CallbackBase:  # type: ignore[no-redef]
        """Fallback base class for local unit tests without Ansible installed."""

        pass


class CallbackModule(CallbackBase):
    """Record Ansible callback events to a JSONL file."""

    CALLBACK_NAME = "ansible_runner_events"
    CALLBACK_NEEDS_ENABLED = True
    CALLBACK_TYPE = "aggregate"
    CALLBACK_VERSION = 2.0

    def v2_playbook_on_play_start(self, play: Any) -> None:
        """Record play start events."""

        self._writeEvent("play_start", play=self._play(play))

    def v2_playbook_on_task_start(
        self,
        task: Any,
        is_conditional: bool = False,
    ) -> None:
        """Record task start events."""

        self._writeEvent(
            "task_start",
            task=self._task(task),
            isConditional=is_conditional,
        )

    def v2_playbook_on_handler_task_start(self, task: Any) -> None:
        """Record handler start events."""

        self._writeEvent("handler_start", task=self._task(task))

    def v2_playbook_on_include(self, included_file: Any) -> None:
        """Record include events."""

        self._writeEvent("include", include=self._include(included_file))

    def v2_runner_on_ok(self, result: Any) -> None:
        """Record successful task result events."""

        self._writeEvent("runner_ok", result=self._result(result))

    def v2_runner_on_failed(
        self,
        result: Any,
        ignore_errors: bool = False,
    ) -> None:
        """Record failed task result events."""

        self._writeEvent(
            "runner_failed",
            result=self._result(result),
            ignoreErrors=ignore_errors,
        )

    def v2_runner_on_unreachable(self, result: Any) -> None:
        """Record unreachable task result events."""

        self._writeEvent("runner_unreachable", result=self._result(result))

    def v2_runner_on_skipped(self, result: Any) -> None:
        """Record skipped task result events."""

        self._writeEvent("runner_skipped", result=self._result(result))

    def v2_runner_item_on_ok(self, result: Any) -> None:
        """Record successful loop-item result events."""

        self._writeEvent("runner_item_ok", result=self._result(result))

    def v2_runner_item_on_failed(self, result: Any) -> None:
        """Record failed loop-item result events."""

        self._writeEvent("runner_item_failed", result=self._result(result))

    def v2_runner_item_on_skipped(self, result: Any) -> None:
        """Record skipped loop-item result events."""

        self._writeEvent("runner_item_skipped", result=self._result(result))

    def v2_playbook_on_stats(self, stats: Any) -> None:
        """Record final playbook stats events."""

        processed = getattr(stats, "processed", {}) or {}
        self._writeEvent("stats", hosts=sorted(processed.keys()))

    def _writeEvent(self, event: str, **payload: Any) -> None:
        """Append one JSONL callback event."""

        logPathText = os.environ.get("ANSIBLE_RUNNER_EVENT_LOG")
        if not logPathText:
            return
        logPath = Path(logPathText)
        logPath.parent.mkdir(parents=True, exist_ok=True)
        record = {
            "event": event,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            **payload,
        }
        with logPath.open("a", encoding="utf-8") as logFile:
            print(json.dumps(record, sort_keys=True, default=str), file=logFile)

    def _play(self, play: Any) -> dict[str, Any]:
        """Extract stable play details."""

        return {
            "name": self._getName(play),
            "uuid": self._getUuid(play),
        }

    def _task(self, task: Any) -> dict[str, Any]:
        """Extract stable task details."""

        role = getattr(task, "_role", None)
        return {
            "action": (
                self._safeCall(getattr(task, "get_action", None))
                or getattr(task, "action", None)
            ),
            "name": self._getName(task),
            "path": self._safeCall(getattr(task, "get_path", None)),
            "role": self._getRoleName(role),
            "uuid": self._getUuid(task),
        }

    def _include(self, included_file: Any) -> dict[str, Any]:
        """Extract include details."""

        return {
            "filename": getattr(included_file, "_filename", None),
            "hosts": self._hosts(getattr(included_file, "_hosts", None)),
            "task": self._task(getattr(included_file, "_task", None)),
        }

    def _result(self, result: Any) -> dict[str, Any]:
        """Extract task result details."""

        host = getattr(result, "_host", None)
        task = getattr(result, "_task", None)
        resultData = getattr(result, "_result", {}) or {}
        return {
            "changed": resultData.get("changed"),
            "host": self._getName(host),
            "item": resultData.get("item"),
            "msg": resultData.get("msg"),
            "rc": resultData.get("rc"),
            "task": self._task(task),
        }

    def _getName(self, value: Any) -> str | None:
        """Return an Ansible object's display name when available."""

        return self._safeCall(getattr(value, "get_name", None))

    def _getRoleName(self, role: Any) -> str | None:
        """Return a role name when task role metadata exists."""

        if role is None:
            return None
        return self._safeCall(getattr(role, "get_name", None)) or str(role)

    def _getUuid(self, value: Any) -> str | None:
        """Return an Ansible object's UUID when available."""

        return self._safeCall(getattr(value, "get_uuid", None))

    def _hosts(self, hosts: Any) -> list[str]:
        """Return stable host names from Ansible include host metadata."""

        if hosts is None:
            return []
        if isinstance(hosts, dict):
            return sorted(str(key) for key in hosts)
        if isinstance(hosts, (list, tuple, set)):
            return sorted(
                self._getName(host) or str(host)
                for host in hosts
            )
        return [str(hosts)]

    @staticmethod
    def _safeCall(method: Any) -> Any:
        """Call a no-argument Ansible accessor defensively."""

        if method is None:
            return None
        try:
            return method()
        except Exception:
            return None
