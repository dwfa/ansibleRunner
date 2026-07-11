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

from ansibleRunner.runner import AnsibleCommandRunner


def testBuildPlaybookCommandMirrorsWrapperFlags() -> None:
    """Verify wrapper-style flags build the expected Ansible command."""

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

    command = AnsibleCommandRunner.buildPlaybookCommand(
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
