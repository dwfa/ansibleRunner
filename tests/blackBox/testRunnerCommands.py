##############################################################################
# Runner command unit tests for ansibleRunner.
#
# USAGE:
#   python3 -m pytest tests/unit/testRunnerCommands.py
#
# WORKFLOW:
#   1. Verify wrapper-style flags build the expected ansible-playbook command.
#
# Copyright 2026 Douglas WF Acheson (dwfa@dwfa.ca)
# Licensed under Apache License 2.0. See LICENSE.md for details.
#
# Version: 1.0
# Date: July 05, 2026
##############################################################################

from __future__ import annotations

from pathlib import Path

from ansibleRunner.runner import AnsibleCommandRunner


def testBuildPlaybookCommandMirrorsWrapperFlags() -> None:
    """Verify wrapper-style flags build the expected Ansible command."""

    runner = AnsibleCommandRunner(Path("/project"), Path("/project/logs"))
    options = AnsibleCommandRunner.parseOptions(
        [
            "-d",
            "-c",
            "-s",
            "-t",
            "-n",
            "dns",
            "--output-level",
            "task",
            "-e",
            "custom=value",
        ]
    )

    command = runner.buildPlaybookCommand(
        "playbooks/site.yaml",
        "dns",
        options,
    )

    assert options.node == "dns"
    assert options.outputLevel == "task"
    assert command == (
        "ansible-playbook",
        "--check",
        "--syntax-check",
        "--list-tasks",
        "--extra-vars",
        "nodes=dns debugFlag=1 newTarget=localhost",
        "-e",
        "custom=value",
        "playbooks/site.yaml",
    )


def testBuildPlaybookCommandPrefersProjectVenvAnsible(tmp_path: Path) -> None:
    """Verify project-local ansible-playbook is used when installed."""

    ansiblePlaybook = tmp_path / ".venv" / "bin" / "ansible-playbook"
    ansiblePlaybook.parent.mkdir(parents=True)
    ansiblePlaybook.write_text("#!/bin/sh\n", encoding="utf-8")
    runner = AnsibleCommandRunner(tmp_path, tmp_path / "logs")

    command = runner.buildPlaybookCommand("playbooks/site.yaml", "dns")

    assert command[0] == str(ansiblePlaybook)


def testBuildPlaybookCommandAllowsMissingNode() -> None:
    """Verify node extra-vars are omitted when no node is configured."""

    runner = AnsibleCommandRunner(Path("/project"), Path("/project/logs"))

    command = runner.buildPlaybookCommand("playbooks/site.yaml", "")

    assert command == ("ansible-playbook", "playbooks/site.yaml")


def testBuildPlaybookCommandKeepsOtherExtraVarsWithoutNode() -> None:
    """Verify non-node extra-vars still pass when no node is configured."""

    runner = AnsibleCommandRunner(Path("/project"), Path("/project/logs"))
    options = AnsibleCommandRunner.parseOptions(["-d"])

    command = runner.buildPlaybookCommand("playbooks/site.yaml", "", options)

    assert command == (
        "ansible-playbook",
        "--extra-vars",
        "debugFlag=1",
        "playbooks/site.yaml",
    )
