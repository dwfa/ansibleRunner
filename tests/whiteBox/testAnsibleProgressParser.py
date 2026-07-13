##############################################################################
# White-box tests for Ansible progress parser.
#
# USAGE:
#   python3 -m pytest tests/whiteBox/testAnsibleProgressParser.py
#
# WORKFLOW:
#   1. Verify Ansible output lines become progress rows.
#   2. Verify output-level filtering and lifecycle state.
#
# Copyright 2026 Douglas WF Acheson (dwfa@dwfa.ca)
# Licensed under Apache License 2.0. See LICENSE.md for details.
#
# Version: 1.0
# Date: July 12, 2026
##############################################################################

from __future__ import annotations

from ansibleRunner.progressParser import AnsibleProgressParser


def testParserShowsActivePlayRoleAndTaskRows() -> None:
    """Verify active output produces emoji play/role/task rows."""

    parser = AnsibleProgressParser(outputLevel="task")

    parser.processLine("PLAY [Build image] ****************", now=1.0)
    parser.processLine("TASK [manageImage : Download image] *****", now=2.0)

    rows = parser.rows(now=4.5)

    assert [(row.depth, row.icon, row.name, row.status) for row in rows] == [
        (0, "🎭", "Build image", "running"),
        (1, "⚙", "manageImage", "running"),
        (2, "🔧", "Download image", "running"),
    ]
    assert rows[0].duration == 3.5
    assert rows[1].duration == 2.5
    assert rows[2].duration == 2.5


def testParserFinalizesCompletedRoleTaskAndPlay() -> None:
    """Verify completed rows have succeeded status and durations."""

    parser = AnsibleProgressParser(outputLevel="task")

    parser.processLine("PLAY [Build image] ****************", now=1.0)
    parser.processLine("TASK [manageImage : Download image] *****", now=2.0)
    parser.processLine("changed: [localhost]", now=4.0)
    parser.finalizePlay(now=5.0)

    rows = parser.rows(now=6.0)

    assert [(row.icon, row.name, row.status) for row in rows] == [
        ("🎭", "Build image", "succeeded"),
        ("⚙", "manageImage", "succeeded"),
        ("🔧", "Download image", "succeeded"),
    ]
    assert rows[0].duration == 4.0
    assert rows[1].duration == 3.0
    assert rows[2].duration == 2.0


def testParserSuppressesSkippedTasks() -> None:
    """Verify skipped tasks are omitted from visible task rows."""

    parser = AnsibleProgressParser(outputLevel="task")

    parser.processLine("PLAY [Build image] ****************", now=1.0)
    parser.processLine("TASK [manageImage : Optional task] *****", now=2.0)
    parser.processLine("skipping: [localhost]", now=3.0)
    parser.finalizePlay(now=4.0)

    rows = parser.rows(now=5.0)

    assert [(row.icon, row.name) for row in rows] == [
        ("🎭", "Build image"),
        ("⚙", "manageImage"),
    ]


def testParserMarksFailures() -> None:
    """Verify fatal output marks active play, role, and task failed."""

    parser = AnsibleProgressParser(outputLevel="task")

    parser.processLine("PLAY [Build image] ****************", now=1.0)
    parser.processLine("TASK [manageImage : Download image] *****", now=2.0)
    parser.processLine("fatal: [localhost]: FAILED!", now=3.0)
    parser.processLine("failed: [localhost]", now=3.1)
    parser.finalizePlay(now=4.0)

    rows = parser.rows(now=5.0)

    assert [row.status for row in rows] == ["failed", "failed", "failed"]


def testParserHonorsRoleOutputLevel() -> None:
    """Verify role output level hides completed task rows."""

    parser = AnsibleProgressParser(outputLevel="role")

    parser.processLine("PLAY [Build image] ****************", now=1.0)
    parser.processLine("TASK [manageImage : Download image] *****", now=2.0)
    parser.processLine("ok: [localhost]", now=3.0)
    parser.finalizePlay(now=4.0)

    rows = parser.rows(now=5.0)

    assert [(row.icon, row.name) for row in rows] == [
        ("🎭", "Build image"),
        ("⚙", "manageImage"),
    ]


def testParserHonorsPlayOutputLevel() -> None:
    """Verify play output level hides role and task rows."""

    parser = AnsibleProgressParser(outputLevel="play")

    parser.processLine("PLAY [Build image] ****************", now=1.0)
    parser.processLine("TASK [manageImage : Download image] *****", now=2.0)
    parser.processLine("ok: [localhost]", now=3.0)
    parser.finalizePlay(now=4.0)

    rows = parser.rows(now=5.0)

    assert [(row.icon, row.name) for row in rows] == [("🎭", "Build image")]


def testParserMarksAbort() -> None:
    """Verify abort marks active items as aborted."""

    parser = AnsibleProgressParser(outputLevel="task")

    parser.processLine("PLAY [Build image] ****************", now=1.0)
    parser.processLine("TASK [manageImage : Download image] *****", now=2.0)
    parser.markAborted(now=3.0)

    rows = parser.rows(now=4.0)

    assert [row.status for row in rows] == ["aborted", "aborted", "aborted"]
