##############################################################################
# Runner execution unit tests for ansibleRunner.
#
# USAGE:
#   python3 -m pytest tests/unit/testRunnerExecution.py
#
# WORKFLOW:
#   1. Verify playbook runs tee output to a project-local log.
#   2. Verify chains stop at the first failing playbook.
#
# Copyright 2026 Douglas WF Acheson (dwfa@dwfa.ca)
# Licensed under Apache License 2.0. See LICENSE.md for details.
#
# Version: 1.0
# Date: July 05, 2026
##############################################################################

from __future__ import annotations

from pathlib import Path
from typing import Any

from ansibleRunner.runner import AnsibleCommandRunner, RunnerOptions


def testRunPlaybookWritesMergedOutputToLog(
    tmp_path: Path,
    monkeypatch: Any,
    capsys: Any,
) -> None:
    """Verify a playbook run streams output to stdout and a log file."""

    _writeFakeAnsible(tmp_path, monkeypatch, exitCode=0)
    playbook = tmp_path / "playbooks" / "site.yaml"
    playbook.parent.mkdir()
    playbook.write_text("---\n", encoding="utf-8")

    runner = AnsibleCommandRunner(tmp_path, tmp_path / "logs")
    result = runner.runPlaybook(
        "playbooks/site.yaml",
        "web",
        RunnerOptions(extraArgs=("--limit", "one")),
    )

    output = capsys.readouterr().out
    assert result.returnCode == 0
    assert result.logPath is not None
    assert result.logPath.is_file()
    assert "Running site playbook ..." in output

    logText = result.logPath.read_text(encoding="utf-8")
    assert "cwd=" + str(tmp_path) in logText
    assert "PYTHONUNBUFFERED=1" in logText
    assert "ANSIBLE_DISPLAY_SKIPPED_HOSTS=false" in logText
    assert "nodes=web" in logText
    assert "--limit" in logText
    assert "one" in logText


def testRunChainStopsAtFirstFailure(tmp_path: Path, monkeypatch: Any) -> None:
    """Verify chained playbook execution returns the first failure code."""

    _writeFakeAnsible(tmp_path, monkeypatch, exitCode=7)
    playbook = tmp_path / "playbooks" / "failing.yaml"
    playbook.parent.mkdir()
    playbook.write_text("---\n", encoding="utf-8")

    runner = AnsibleCommandRunner(tmp_path, tmp_path / "logs")

    result = runner.runChain(
        [
            ("playbooks/failing.yaml", "default"),
            ("playbooks/missing.yaml", "default"),
        ],
        ["-n", "override"],
    )

    assert result == 7


def _writeFakeAnsible(tmp_path: Path, monkeypatch: Any, exitCode: int) -> None:
    """Write a fake ansible-playbook executable into a temporary PATH."""

    binDir = tmp_path / "bin"
    binDir.mkdir()
    executable = binDir / "ansible-playbook"
    executable.write_text(
        "#!/bin/sh\n"
        "echo cwd=$(pwd)\n"
        "echo PYTHONUNBUFFERED=$PYTHONUNBUFFERED\n"
        "echo ANSIBLE_DISPLAY_SKIPPED_HOSTS=$ANSIBLE_DISPLAY_SKIPPED_HOSTS\n"
        "for arg in \"$@\"; do\n"
        "  echo $arg\n"
        "done\n"
        f"exit {exitCode}\n",
        encoding="utf-8",
    )
    executable.chmod(0o755)
    monkeypatch.setenv("PATH", f"{binDir}:{tmp_path}")
