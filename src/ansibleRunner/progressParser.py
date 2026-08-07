##############################################################################
# Ansible progress parser.
#
# USAGE:
#   parser = AnsibleProgressParser(outputLevel="role")
#   parser.processLine("PLAY [site] ***")
#   rows = parser.rows()
#
# Copyright 2026 Douglas WF Acheson (dwfa@dwfa.ca)
# Licensed under Apache License 2.0. See LICENSE.md for details.
#
# Version: 1.0
# Date: July 12, 2026
##############################################################################

"""Parse Ansible output into progress display rows."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Literal


OutputLevel = Literal["play", "role", "task"]


PLAY_PATTERN = re.compile(r"^PLAY \[(.+?)\] \*+\s*$")
TASK_PATTERN = re.compile(r"^TASK \[(.+?)\] \*+\s*$")
HANDLER_PATTERN = re.compile(r"^RUNNING HANDLER \[(.+?)\] \*+\s*$")
AR_HIDE_HINT_PATTERN = re.compile(r"(?:^|\s)@ar:hide(?:\s|$)")
FATAL_PATTERN = re.compile(r"^fatal: \[.+?\]:")
INCLUDED_PATTERN = re.compile(r"^included: .+ for .+$")
RESULT_PATTERN = re.compile(
    r"^(ok|changed|failed|fatal|unreachable|skipping): \[.+?\]"
)
ANSI_PATTERN = re.compile(r"\x1b\[[0-9;]*m")


@dataclass
class PrettyOutput:
    """Human-friendly output block associated with a progress task.

    Args:
        body: Preformatted body text.
        hideTaskRow: Whether the owning task row should be hidden in the tree.
        title: Short output title.
    """

    title: str
    body: str
    hideTaskRow: bool = False


@dataclass
class ProgressItem:
    """Mutable parsed progress item.

    Args:
        name: Display name.
        startTime: Start time in seconds.
        aborted: Whether this item was aborted.
        duration: Completed duration in seconds.
        failed: Whether this item failed.
        result: Optional interaction result text.
        interactions: Prompt interactions under this item.
        outputs: Human-friendly output blocks associated with this item.
        roles: Child role items.
        sawExecutedResult: Whether a task had a non-skipped result.
        sawResult: Whether a task had any result line.
        tasks: Child task items.
    """

    name: str
    startTime: float
    aborted: bool = False
    duration: float = 0.0
    failed: bool = False
    result: str = ""
    interactions: list["ProgressItem"] = field(default_factory=list)
    hidden: bool = False
    outputs: list[PrettyOutput] = field(default_factory=list)
    roles: list["ProgressItem"] = field(default_factory=list)
    sawExecutedResult: bool = False
    sawResult: bool = False
    tasks: list["ProgressItem"] = field(default_factory=list)


@dataclass(frozen=True)
class ProgressRow:
    """Display row for parsed Ansible progress.

    Args:
        depth: Tree depth.
        duration: Elapsed or completed duration in seconds.
        icon: Emoji indicating item type.
        name: Display name.
        output: Optional pretty output block.
        status: ``running``, ``succeeded``, ``failed``, or ``aborted``.
    """

    depth: int
    duration: float
    icon: str
    name: str
    status: str
    output: PrettyOutput | None = None


class AnsibleProgressParser:
    """Parse Ansible stdout lines into a progress hierarchy.

    Args:
        outputLevel: Display detail level: ``play``, ``role``, or ``task``.
    """

    def __init__(self, outputLevel: OutputLevel = "role") -> None:
        """Initialize parser state."""

        self.completedPlays: list[ProgressItem] = []
        self.currentPlay: ProgressItem | None = None
        self.currentRole: ProgressItem | None = None
        self.currentTask: ProgressItem | None = None
        self.idleStartTime: float | None = None
        self.outputLevel: OutputLevel = outputLevel
        self.syntheticTaskAliases: set[str] = set()

    def processLine(self, line: str, now: float) -> None:
        """Process one cleaned Ansible output line.

        Args:
            line: Cleaned output line without trailing newline.
            now: Timestamp for this parser event.
        """

        cleanLine = ANSI_PATTERN.sub("", line)

        playMatch = PLAY_PATTERN.match(cleanLine)
        if playMatch:
            playName, hidden = self._displayNameAndHidden(playMatch.group(1))
            if (
                self.currentPlay is not None
                and self.currentPlay.name == playName
            ):
                return
            self.finalizePlay(now)
            self.currentPlay = ProgressItem(playName, now, hidden=hidden)
            self.idleStartTime = None
            return

        taskMatch = TASK_PATTERN.match(cleanLine) or HANDLER_PATTERN.match(cleanLine)
        if taskMatch:
            taskHeader = taskMatch.group(1)
            if self._matchesSyntheticTaskAlias(taskHeader):
                return
            self._startTask(taskHeader, now)
            return

        if INCLUDED_PATTERN.match(cleanLine):
            self._suppressCurrentTask(now)
            return

        if FATAL_PATTERN.match(cleanLine):
            self._markFailure()
            return

        resultMatch = RESULT_PATTERN.match(cleanLine)
        if resultMatch and self.currentTask is not None:
            resultState = resultMatch.group(1)
            self.currentTask.sawResult = True
            if resultState != "skipping":
                self.currentTask.sawExecutedResult = True
            if resultState in {"failed", "fatal", "unreachable"}:
                self.currentTask.failed = True
                self._markFailure()
            self._finalizeTask(now)

    def rows(self, now: float) -> list[ProgressRow]:
        """Return display rows for the current parser state.

        Args:
            now: Current timestamp for active item elapsed times.

        Returns:
            Parsed progress rows.
        """

        rows: list[ProgressRow] = []
        for play in self.completedPlays:
            self._appendPlayRows(rows, play, now, isActive=False)
        if self.currentPlay is not None:
            self._appendPlayRows(rows, self.currentPlay, now, isActive=True)
        return rows

    def finalizePlay(self, now: float) -> None:
        """Finalize the active play.

        Args:
            now: Timestamp for completed durations.
        """

        if self.currentPlay is None:
            return
        self._finalizeTask(now)
        self._finalizeRole(now)
        self.currentPlay.duration = now - self.currentPlay.startTime
        self.completedPlays.append(self.currentPlay)
        self.currentPlay = None

    def markAborted(self, now: float) -> None:
        """Mark current active items as aborted.

        Args:
            now: Timestamp for completed durations.
        """

        if self.currentPlay is not None:
            self.currentPlay.aborted = True
        if self.currentRole is not None:
            self.currentRole.aborted = True
        if self.currentTask is not None:
            self.currentTask.aborted = True
        self.finalizePlay(now)

    def suppressActiveTask(self, now: float) -> None:
        """Suppress the active task as structural/internal output.

        Args:
            now: Timestamp for the structural output.
        """

        self._suppressCurrentTask(now)

    def startSyntheticTask(
        self,
        taskHeader: str,
        now: float,
        aliases: set[str] | None = None,
    ) -> None:
        """Start a predicted task before Ansible emits its real task header.

        Args:
            aliases: Real task headers that should merge into the synthetic task.
            now: Timestamp for the synthetic task start.
            taskHeader: Display task header in Ansible ``role : task`` form.
        """

        self._startTask(taskHeader, now, useIdleStart=False)
        self.syntheticTaskAliases = {
            self._normalizeTaskHeader(alias) for alias in (aliases or set())
        }

    def startSyntheticTaskFromCurrentRole(
        self,
        taskName: str,
        now: float,
        aliases: set[str] | None = None,
    ) -> None:
        """Start a predicted task under the currently active role.

        Args:
            aliases: Real task names that should merge into the synthetic task.
            now: Timestamp for the synthetic task start.
            taskName: Display task name without the role prefix.
        """

        if self.currentRole is None:
            return
        roleName = self.currentRole.name
        self.startSyntheticTask(
            f"{roleName} : {taskName}",
            now,
            {
                f"{roleName} : {alias}"
                for alias in (aliases or set())
            },
        )

    def _appendPlayRows(
        self,
        rows: list[ProgressRow],
        play: ProgressItem,
        now: float,
        isActive: bool,
    ) -> None:
        """Append one play and visible descendants to rows."""

        baseDepth = 0
        if play.hidden:
            baseDepth = -1
        else:
            rows.append(self._row(0, "🎭", play, now, isActive))
        if self.outputLevel == "play":
            return
        if self.outputLevel == "task" or not self._hasVisibleTaskOutput(play):
            for interaction in play.interactions:
                rows.append(
                    self._row(
                        max(0, baseDepth + 1),
                        "💬",
                        interaction,
                        now,
                        False,
                    )
                )
        for role in play.roles:
            roleDepth = max(0, baseDepth + 1)
            taskDepth = roleDepth + 1
            if not role.hidden:
                rows.append(self._row(roleDepth, "⚙", role, now, False))
            else:
                taskDepth = roleDepth
            if self.outputLevel == "task" or self._hasVisibleTaskOutput(role):
                for task in role.tasks:
                    self._appendTaskRows(
                        rows,
                        taskDepth,
                        task,
                        now,
                        False,
                        showTask=self.outputLevel == "task",
                    )
            if self.outputLevel == "task" or not self._hasVisibleTaskOutput(role):
                for interaction in role.interactions:
                    rows.append(self._row(taskDepth, "💬", interaction, now, False))
        if isActive and self.currentRole is not None:
            roleDepth = max(0, baseDepth + 1)
            taskDepth = roleDepth + 1
            if not self.currentRole.hidden:
                rows.append(self._row(roleDepth, "⚙", self.currentRole, now, True))
            else:
                taskDepth = roleDepth
            if self.outputLevel == "task" or self._hasVisibleTaskOutput(
                self.currentRole
            ):
                for task in self.currentRole.tasks:
                    self._appendTaskRows(
                        rows,
                        taskDepth,
                        task,
                        now,
                        False,
                        showTask=self.outputLevel == "task",
                    )
            if self.outputLevel == "task" or not self._hasVisibleTaskOutput(
                self.currentRole
            ):
                for interaction in self.currentRole.interactions:
                    rows.append(self._row(taskDepth, "💬", interaction, now, False))
            if (
                self.currentTask is not None
                and self._taskIsVisible(self.currentTask)
                and (self.outputLevel == "task" or bool(self.currentTask.outputs))
            ):
                self._appendTaskRows(
                    rows,
                    taskDepth,
                    self.currentTask,
                    now,
                    True,
                    showTask=self.outputLevel == "task",
                )
        elif isActive and self.currentTask is not None:
            if (
                self._taskIsVisible(self.currentTask)
                and (self.outputLevel == "task" or bool(self.currentTask.outputs))
            ):
                self._appendTaskRows(
                    rows,
                    max(0, baseDepth + 1),
                    self.currentTask,
                    now,
                    True,
                    showTask=self.outputLevel == "task",
                )
        if self.outputLevel == "task" or self._hasVisibleTaskOutput(play):
            for task in play.tasks:
                self._appendTaskRows(
                    rows,
                    max(0, baseDepth + 1),
                    task,
                    now,
                    False,
                    showTask=self.outputLevel == "task",
                )

    def _appendTaskRows(
        self,
        rows: list[ProgressRow],
        depth: int,
        task: ProgressItem,
        now: float,
        isActive: bool,
        showTask: bool = True,
    ) -> None:
        """Append a task row and any task output blocks."""

        hideOutputTaskRow = bool(task.outputs) and all(
            output.hideTaskRow for output in task.outputs
        )
        showOutputTaskRow = any(not output.hideTaskRow for output in task.outputs)
        showVisibleTaskRow = not task.hidden and (
            (showTask and not hideOutputTaskRow) or showOutputTaskRow
        )
        if showVisibleTaskRow:
            rows.append(self._row(depth, "🔧", task, now, isActive))
        for output in task.outputs:
            rows.append(
                ProgressRow(
                    depth=depth + 1 if showVisibleTaskRow else depth,
                    duration=0.0,
                    icon="",
                    name="",
                    status="succeeded",
                    output=output,
                )
            )

    @staticmethod
    def _hasVisibleTaskOutput(item: ProgressItem) -> bool:
        """Return whether an item has child task output blocks."""

        return any(task.outputs for task in item.tasks) or any(
            task.outputs
            for role in item.roles
            for task in role.tasks
        )

    def _finalizeRole(self, now: float) -> None:
        """Finalize the active role."""

        if self.currentRole is None or self.currentPlay is None:
            return
        self._finalizeTask(now)
        self.currentRole.duration = now - self.currentRole.startTime
        self.currentPlay.roles.append(self.currentRole)
        self.currentRole = None

    def _finalizeTask(self, now: float) -> None:
        """Finalize the active task."""

        if self.currentTask is None or self.currentPlay is None:
            return
        if self.currentTask.sawResult and not self.currentTask.sawExecutedResult:
            self.currentTask = None
            self.idleStartTime = now
            self.syntheticTaskAliases = set()
            return
        self.currentTask.duration = now - self.currentTask.startTime
        if self.currentRole is not None:
            self.currentRole.tasks.append(self.currentTask)
        else:
            self.currentPlay.tasks.append(self.currentTask)
        self.currentTask = None
        self.idleStartTime = now
        self.syntheticTaskAliases = set()

    def _markFailure(self) -> None:
        """Mark active items as failed."""

        if self.currentPlay is not None:
            self.currentPlay.failed = True
        if self.currentRole is not None:
            self.currentRole.failed = True
        if self.currentTask is not None:
            self.currentTask.failed = True

    def _suppressCurrentTask(self, now: float) -> None:
        """Finalize the active task as structural output.

        Args:
            now: Timestamp for the structural include output.
        """

        if self.currentTask is None:
            return
        self.currentTask.sawResult = True
        self.currentTask.sawExecutedResult = False
        self._finalizeTask(now)

    def recordInteraction(
        self,
        message: str,
        value: str,
        duration: float,
        aborted: bool = False,
        failed: bool = False,
    ) -> None:
        """Record a completed prompt interaction.

        Args:
            message: Prompt message shown to the user.
            value: User-facing response result.
            duration: Time spent handling the prompt.
            aborted: Whether the interaction aborted the run.
            failed: Whether the interaction failed before completion.
        """

        if self.currentPlay is None:
            return
        interaction = ProgressItem(
            name=f"{message} — {value}",
            startTime=0.0,
            aborted=aborted,
            duration=duration,
            failed=failed,
            result=value,
        )
        if self.currentRole is not None:
            self.currentRole.interactions.append(interaction)
            return
        self.currentPlay.interactions.append(interaction)

    def recordTaskOutput(
        self,
        taskHeader: str,
        title: str,
        body: str,
        hideTaskRow: bool = False,
    ) -> None:
        """Record a human-friendly output block for a task.

        Args:
            body: Preformatted output body.
            hideTaskRow: Whether to suppress the owning task row in display rows.
            taskHeader: Ansible task header in optional ``role : task`` form.
            title: Short block title.
        """

        targetTask = self._findTaskByHeader(taskHeader)
        if targetTask is None:
            return
        targetTask.outputs.append(
            PrettyOutput(title=title, body=body, hideTaskRow=hideTaskRow)
        )

    @staticmethod
    def _row(
        depth: int,
        icon: str,
        item: ProgressItem,
        now: float,
        isActive: bool,
    ) -> ProgressRow:
        """Build a display row from a progress item."""

        if item.aborted:
            status = "aborted"
        elif item.failed:
            status = "failed"
        elif isActive:
            status = "running"
        else:
            status = "succeeded"
        duration = now - item.startTime if isActive else item.duration
        return ProgressRow(
            depth=depth,
            duration=duration,
            icon=icon,
            name=item.name,
            status=status,
        )

    def _startRole(self, roleName: str, now: float) -> None:
        """Start a role if it is not already active."""

        if self.currentPlay is None:
            return
        roleName, hidden = self._displayNameAndHidden(roleName)
        if self.currentRole is not None and self.currentRole.name == roleName:
            self.currentRole.hidden = self.currentRole.hidden or hidden
            return
        self._finalizeRole(now)
        self.currentRole = ProgressItem(roleName, now, hidden=hidden)

    def _startTask(
        self,
        taskHeader: str,
        now: float,
        useIdleStart: bool = True,
    ) -> None:
        """Start a task, inferring role from Ansible task header."""

        if self.currentPlay is None:
            return
        if self._matchesCurrentTask(taskHeader):
            return
        taskStartTime = (
            self.idleStartTime
            if useIdleStart and self.currentTask is None
            else None
        )
        self._finalizeTask(now)
        if taskStartTime is None:
            taskStartTime = now
        if " : " in taskHeader:
            roleName, taskName = taskHeader.split(" : ", 1)
            self._startRole(roleName, taskStartTime)
        else:
            self._finalizeRole(now)
            taskName = taskHeader
        taskName, hidden = self._displayNameAndHidden(taskName)
        if self._reopenLastCompletedTask(taskName, taskStartTime):
            if self.currentTask is not None:
                self.currentTask.hidden = self.currentTask.hidden or hidden
            self.idleStartTime = None
            return
        self.currentTask = ProgressItem(taskName, taskStartTime, hidden=hidden)
        self.idleStartTime = None

    @staticmethod
    def _taskIsVisible(task: ProgressItem) -> bool:
        """Return whether a task should be shown in progress rows."""

        return not task.sawResult or task.sawExecutedResult

    def _reopenLastCompletedTask(self, taskName: str, startTime: float) -> bool:
        """Reopen a just-completed task when another stream repeats its header."""

        targetTasks: list[ProgressItem]
        if self.currentRole is not None:
            targetTasks = self.currentRole.tasks
        elif self.currentPlay is not None:
            targetTasks = self.currentPlay.tasks
        else:
            return False
        if not targetTasks:
            return False
        lastTask = targetTasks[-1]
        if self._normalizeTaskHeader(lastTask.name) != self._normalizeTaskHeader(
            taskName,
        ):
            return False
        self.currentTask = targetTasks.pop()
        self.currentTask.startTime = min(self.currentTask.startTime, startTime)
        return True

    def _matchesSyntheticTaskAlias(self, taskHeader: str) -> bool:
        """Return whether an Ansible header should merge into a synthetic task."""

        return (
            self.currentTask is not None
            and self._normalizeTaskHeader(taskHeader) in self.syntheticTaskAliases
        )

    def _matchesCurrentTask(self, taskHeader: str) -> bool:
        """Return whether a task header repeats the currently active task."""

        if self.currentTask is None:
            return False
        if " : " in taskHeader:
            roleName, taskName = taskHeader.split(" : ", 1)
            roleName, _hidden = self._displayNameAndHidden(roleName)
            currentRoleName = (
                self.currentRole.name if self.currentRole is not None else None
            )
            return (
                currentRoleName == roleName
                and self._normalizeTaskHeader(self.currentTask.name)
                == self._normalizeTaskHeader(taskName)
            )
        return (
            self.currentRole is None
            and self._normalizeTaskHeader(self.currentTask.name)
            == self._normalizeTaskHeader(taskHeader)
        )

    def _findTaskByHeader(self, taskHeader: str) -> ProgressItem | None:
        """Return the active or completed task matching a task header."""

        roleName = None
        taskName = taskHeader
        if " : " in taskHeader:
            roleName, taskName = taskHeader.split(" : ", 1)
            roleName, _hidden = self._displayNameAndHidden(roleName)
        normalizedTaskName = self._normalizeTaskHeader(taskName)

        if self._matchesCurrentTask(taskHeader):
            return self.currentTask
        if roleName is not None and self.currentRole is not None:
            if self.currentRole.name == roleName:
                for task in reversed(self.currentRole.tasks):
                    if self._normalizeTaskHeader(task.name) == normalizedTaskName:
                        return task
        if roleName is None and self.currentPlay is not None:
            for task in reversed(self.currentPlay.tasks):
                if self._normalizeTaskHeader(task.name) == normalizedTaskName:
                    return task
        if self.currentPlay is not None:
            for role in reversed(self.currentPlay.roles):
                if roleName is not None and role.name != roleName:
                    continue
                for task in reversed(role.tasks):
                    if self._normalizeTaskHeader(task.name) == normalizedTaskName:
                        return task
        return None

    @staticmethod
    def _normalizeTaskHeader(taskHeader: str) -> str:
        """Normalize task headers for alias matching."""

        displayName, _hidden = AnsibleProgressParser._displayNameAndHidden(taskHeader)
        return " ".join(displayName.lower().split())

    @staticmethod
    def _displayNameAndHidden(name: str) -> tuple[str, bool]:
        """Return display name and whether it carries the AR hide hint."""

        hidden = bool(AR_HIDE_HINT_PATTERN.search(name))
        displayName = AR_HIDE_HINT_PATTERN.sub(" ", name)
        return " ".join(displayName.split()), hidden
