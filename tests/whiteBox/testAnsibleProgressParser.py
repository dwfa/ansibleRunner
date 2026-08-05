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


def testParserIgnoresRepeatedActiveTaskHeader() -> None:
    """Verify callback-first and stdout-later task headers do not duplicate."""

    parser = AnsibleProgressParser(outputLevel="task")

    parser.processLine("PLAY [Build image] ****************", now=1.0)
    parser.processLine("TASK [manageImage : Download image] *****", now=2.0)
    parser.processLine("TASK [manageImage : Download image] *****", now=4.0)

    rows = parser.rows(now=5.0)

    assert [(row.icon, row.name, row.status) for row in rows] == [
        ("🎭", "Build image", "running"),
        ("⚙", "manageImage", "running"),
        ("🔧", "Download image", "running"),
    ]
    assert rows[2].duration == 3.0


def testParserIgnoresRepeatedActivePlayHeader() -> None:
    """Verify callback-first and stdout-later play headers do not duplicate."""

    parser = AnsibleProgressParser(outputLevel="role")

    parser.processLine("PLAY [Build image] ****************", now=1.0)
    parser.processLine("PLAY [Build image] ****************", now=2.0)
    parser.processLine("TASK [manageImage : Download image] *****", now=3.0)
    parser.processLine("ok: [localhost]", now=4.0)
    parser.finalizePlay(now=5.0)

    rows = parser.rows(now=6.0)

    assert [(row.icon, row.name) for row in rows] == [
        ("🎭", "Build image"),
        ("⚙", "manageImage"),
    ]


def testParserRecordsPrettyTaskOutput() -> None:
    """Verify task output blocks render below their owning task row."""

    parser = AnsibleProgressParser(outputLevel="task")

    parser.processLine("PLAY [List servers] ****************", now=1.0)
    parser.processLine("TASK [listDBServers : niceDisplay: Server summary] *****", now=2.0)
    parser.recordTaskOutput(
        "listDBServers : niceDisplay: Server summary",
        "Server summary",
        "NAME  LOCATION\n----  --------\ndb1   East US",
    )
    parser.processLine("ok: [localhost]", now=3.0)
    parser.finalizePlay(now=4.0)

    rows = parser.rows(now=5.0)

    assert [(row.icon, row.name, row.output is not None) for row in rows] == [
        ("🎭", "List servers", False),
        ("⚙", "listDBServers", False),
        ("🔧", "niceDisplay: Server summary", False),
        ("", "", True),
    ]
    assert rows[3].output is not None
    assert rows[3].output.title == "Server summary"
    assert "db1   East US" in rows[3].output.body


def testParserShowsPrettyTaskOutputAtRoleLevel() -> None:
    """Verify pretty task output remains visible when task rows are hidden."""

    parser = AnsibleProgressParser(outputLevel="role")

    parser.processLine("PLAY [List servers] ****************", now=1.0)
    parser.processLine("TASK [niceDisplay: Server summary] *****", now=2.0)
    parser.recordTaskOutput(
        "niceDisplay: Server summary",
        "Server summary",
        "NAME\n----\ndb1",
    )
    parser.processLine("ok: [localhost]", now=3.0)
    parser.finalizePlay(now=4.0)

    rows = parser.rows(now=5.0)

    assert [(row.icon, row.name, row.output is not None) for row in rows] == [
        ("🎭", "List servers", False),
        ("🔧", "niceDisplay: Server summary", False),
        ("", "", True),
    ]


def testParserCanHidePrettyOutputTaskRow() -> None:
    """Verify marked pretty output can render without its owning task row."""

    parser = AnsibleProgressParser(outputLevel="role")

    parser.processLine("PLAY [List servers] ****************", now=1.0)
    parser.processLine("TASK [niceDisplay: Server summary] *****", now=2.0)
    parser.recordTaskOutput(
        "niceDisplay: Server summary",
        "Server summary",
        "NAME\n----\ndb1",
        hideTaskRow=True,
    )
    parser.processLine("ok: [localhost]", now=3.0)
    parser.finalizePlay(now=4.0)

    rows = parser.rows(now=5.0)

    assert [(row.icon, row.name, row.output is not None) for row in rows] == [
        ("🎭", "List servers", False),
        ("", "", True),
    ]


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


def testParserAttributesQuietGapToNextTask() -> None:
    """Verify delayed task headers receive the preceding quiet elapsed time."""

    parser = AnsibleProgressParser(outputLevel="task")

    parser.processLine("PLAY [Create RPi Image] ****************", now=1.0)
    parser.processLine("TASK [createRPiImage : Set image path (remote)] *****", now=2.0)
    parser.processLine("ok: [installer]", now=3.0)
    parser.processLine("TASK [createRPiImage : Copy image to remote host] *****", now=68.0)
    parser.processLine("changed: [installer]", now=68.0)
    parser.finalizePlay(now=69.0)

    rows = parser.rows(now=70.0)

    assert [(row.icon, row.name, row.status) for row in rows] == [
        ("🎭", "Create RPi Image", "succeeded"),
        ("⚙", "createRPiImage", "succeeded"),
        ("🔧", "Set image path (remote)", "succeeded"),
        ("🔧", "Copy image to remote host", "succeeded"),
    ]
    assert rows[2].duration == 1.0
    assert rows[3].duration == 65.0


def testParserMergesRealTaskHeaderIntoSyntheticTask() -> None:
    """Verify predicted tasks stay active until their real result arrives."""

    parser = AnsibleProgressParser(outputLevel="task")

    parser.processLine("PLAY [Create RPi Image] ****************", now=1.0)
    parser.processLine("TASK [createRPiImage : confirm write operation] *****", now=2.0)
    parser.processLine("ok: [installer]", now=3.0)
    parser.startSyntheticTask(
        "createRPiImage : Writing image to device",
        now=3.0,
        aliases={"createRPiImage : write image to device"},
    )

    rows = parser.rows(now=53.0)

    assert [(row.icon, row.name, row.status) for row in rows] == [
        ("🎭", "Create RPi Image", "running"),
        ("⚙", "createRPiImage", "running"),
        ("🔧", "confirm write operation", "succeeded"),
        ("🔧", "Writing image to device", "running"),
    ]
    assert rows[3].duration == 50.0

    parser.processLine("TASK [createRPiImage : write image to device] *****", now=63.0)
    parser.processLine("changed: [installer]", now=63.0)
    parser.finalizePlay(now=64.0)
    rows = parser.rows(now=65.0)

    assert [(row.icon, row.name, row.status) for row in rows] == [
        ("🎭", "Create RPi Image", "succeeded"),
        ("⚙", "createRPiImage", "succeeded"),
        ("🔧", "confirm write operation", "succeeded"),
        ("🔧", "Writing image to device", "succeeded"),
    ]
    assert rows[3].duration == 60.0


def testParserStartsSyntheticTaskFromCurrentRole() -> None:
    """Verify predicted task helpers use the active role context."""

    parser = AnsibleProgressParser(outputLevel="task")

    parser.processLine("PLAY [Create RPi Image] ****************", now=1.0)
    parser.processLine("TASK [createRPiImage : Set image path (remote)] *****", now=2.0)
    parser.processLine("ok: [installer]", now=3.0)
    parser.startSyntheticTaskFromCurrentRole(
        "Copy image to remote host",
        now=3.0,
        aliases={"Copy image to remote host"},
    )

    rows = parser.rows(now=33.0)

    assert [(row.icon, row.name, row.status) for row in rows] == [
        ("🎭", "Create RPi Image", "running"),
        ("⚙", "createRPiImage", "running"),
        ("🔧", "Set image path (remote)", "succeeded"),
        ("🔧", "Copy image to remote host", "running"),
    ]
    assert rows[3].duration == 30.0


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


def testParserSuppressesIncludedTasks() -> None:
    """Verify include_tasks wrapper rows are omitted from visible task rows."""

    parser = AnsibleProgressParser(outputLevel="task")

    parser.processLine("PLAY [Build image] ****************", now=1.0)
    parser.processLine("TASK [manageImage : Load setup tasks] *****", now=2.0)
    parser.processLine(
        "included: /tmp/tasks/setup.yaml for localhost",
        now=2.5,
    )
    parser.processLine("TASK [manageImage : Configure service] *****", now=3.0)
    parser.processLine("ok: [localhost]", now=4.0)
    parser.finalizePlay(now=5.0)

    rows = parser.rows(now=6.0)

    assert [(row.icon, row.name) for row in rows] == [
        ("🎭", "Build image"),
        ("⚙", "manageImage"),
        ("🔧", "Configure service"),
    ]


def testParserSuppressesPromptImplementationTask() -> None:
    """Verify prompt implementation tasks can be hidden from progress rows."""

    parser = AnsibleProgressParser(outputLevel="task")

    parser.processLine("PLAY [Create image] ****************", now=1.0)
    parser.processLine("TASK [getInstallDevice : wait for user input] *****", now=2.0)
    parser.suppressActiveTask(now=2.1)
    parser.processLine("ok: [installer]", now=3.0)
    parser.processLine("TASK [getInstallDevice : Next task] *****", now=4.0)
    parser.processLine("ok: [installer]", now=5.0)
    parser.finalizePlay(now=6.0)

    rows = parser.rows(now=7.0)

    assert [(row.icon, row.name) for row in rows] == [
        ("🎭", "Create image"),
        ("⚙", "getInstallDevice"),
        ("🔧", "Next task"),
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


def testParserShowsPromptInteractionsUnderActiveRole() -> None:
    """Verify prompt interactions render under the current role."""

    parser = AnsibleProgressParser(outputLevel="role")

    parser.processLine("PLAY [Prompt play] ****************", now=1.0)
    parser.processLine("TASK [pause : wait of input to continue] *****", now=2.0)
    parser.recordInteraction("wait of input to continue", "continued", 0.5)
    parser.processLine("ok: [localhost]", now=3.0)
    parser.finalizePlay(now=4.0)

    rows = parser.rows(now=5.0)

    assert [(row.depth, row.icon, row.name, row.status) for row in rows] == [
        (0, "🎭", "Prompt play", "succeeded"),
        (1, "⚙", "pause", "succeeded"),
        (2, "💬", "wait of input to continue — continued", "succeeded"),
    ]
    assert rows[2].duration == 0.5
