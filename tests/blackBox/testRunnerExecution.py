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

import os
from pathlib import Path
from threading import Timer
from textwrap import dedent
from typing import Any

from ansibleRunner.runner import AnsibleCommandRunner, RunControl, RunnerOptions


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


def testRunPlaybookSendsMergedOutputToHandler(
    tmp_path: Path,
    monkeypatch: Any,
) -> None:
    """Verify a playbook run sends merged output to a callback."""

    _writeFakeAnsible(tmp_path, monkeypatch, exitCode=0)
    playbook = tmp_path / "playbooks" / "site.yaml"
    playbook.parent.mkdir()
    playbook.write_text("---\n", encoding="utf-8")
    outputLines: list[str] = []

    runner = AnsibleCommandRunner(tmp_path, tmp_path / "logs")
    result = runner.runPlaybook(
        "playbooks/site.yaml",
        "web",
        outputHandler=outputLines.append,
    )

    assert result.returnCode == 0
    assert any("cwd=" + str(tmp_path) in line for line in outputLines)
    assert any("nodes=web" in line for line in outputLines)


def testRunPlaybookCanBeCanceled(tmp_path: Path, monkeypatch: Any) -> None:
    """Verify cancellation terminates a running playbook."""

    _writeSlowFakeAnsible(tmp_path, monkeypatch)
    playbook = tmp_path / "playbooks" / "slow.yaml"
    playbook.parent.mkdir()
    playbook.write_text("---\n", encoding="utf-8")
    runControl = RunControl()

    timer = Timer(0.2, runControl.cancel)
    timer.start()
    try:
        runner = AnsibleCommandRunner(tmp_path, tmp_path / "logs")
        result = runner.runPlaybook(
            "playbooks/slow.yaml",
            "web",
            echoOutput=False,
            runControl=runControl,
        )
    finally:
        timer.cancel()

    assert result.returnCode == 130
    assert runControl.cancelled


def testRunPlaybookCanReceiveInput(tmp_path: Path, monkeypatch: Any) -> None:
    """Verify input can be sent to a running playbook."""

    _writeInputFakeAnsible(tmp_path, monkeypatch)
    playbook = tmp_path / "playbooks" / "input.yaml"
    playbook.parent.mkdir()
    playbook.write_text("---\n", encoding="utf-8")
    outputLines: list[str] = []
    runControl = RunControl()

    timer = Timer(0.2, lambda: runControl.sendInput("\n"))
    timer.start()
    try:
        runner = AnsibleCommandRunner(tmp_path, tmp_path / "logs")
        result = runner.runPlaybook(
            "playbooks/input.yaml",
            "web",
            echoOutput=False,
            outputHandler=outputLines.append,
            runControl=runControl,
        )
    finally:
        timer.cancel()

    assert result.returnCode == 0
    assert any("waiting for input" in line for line in outputLines)
    assert any("continued" in line for line in outputLines)


def testRunPlaybookPrunesOldRunLogs(tmp_path: Path, monkeypatch: Any) -> None:
    """Verify playbook run logs keep only the newest five files."""

    _writeFakeAnsible(tmp_path, monkeypatch, exitCode=0)
    playbook = tmp_path / "playbooks" / "site.yaml"
    playbook.parent.mkdir()
    playbook.write_text("---\n", encoding="utf-8")
    logDir = tmp_path / "logs"
    logDir.mkdir()
    for index in range(7):
        logPath = logDir / f"site-20260719-12000{index}.log"
        logPath.write_text(f"old {index}\n", encoding="utf-8")
        os.utime(logPath, (index, index))
    unrelatedLog = logDir / "shim-20260719-120000.log"
    unrelatedLog.write_text("shim\n", encoding="utf-8")

    runner = AnsibleCommandRunner(tmp_path, logDir)
    result = runner.runPlaybook("playbooks/site.yaml", "web", echoOutput=False)

    assert result.returnCode == 0
    assert len(sorted(logDir.glob("site-*.log"))) == 5
    assert unrelatedLog.is_file()


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
    monkeypatch.setenv("PATH", f"{binDir}:{tmp_path}:{os.environ.get('PATH', '')}")


def _writeInputFakeAnsible(tmp_path: Path, monkeypatch: Any) -> None:
    """Write a fake ansible-playbook executable that waits for input."""

    binDir = tmp_path / "bin"
    binDir.mkdir()
    executable = binDir / "ansible-playbook"
    executable.write_text(
        "#!/usr/bin/env python3\n"
        + dedent(
            """
            import sys

            print("waiting for input", flush=True)
            sys.stdin.readline()
            print("continued", flush=True)
            sys.exit(0)
            """
        ).lstrip(),
        encoding="utf-8",
    )
    executable.chmod(0o755)
    monkeypatch.setenv("PATH", f"{binDir}:{tmp_path}:{os.environ.get('PATH', '')}")


def _writeSlowFakeAnsible(tmp_path: Path, monkeypatch: Any) -> None:
    """Write a fake ansible-playbook executable that waits indefinitely."""

    binDir = tmp_path / "bin"
    binDir.mkdir()
    executable = binDir / "ansible-playbook"
    executable.write_text(
        "#!/usr/bin/env python3\n"
        + dedent(
            """
            import signal
            import sys
            import time

            def stop(signum, frame):
                print("stopped", flush=True)
                sys.exit(130)

            signal.signal(signal.SIGTERM, stop)
            print("started", flush=True)
            while True:
                time.sleep(1)
            """
        ).lstrip(),
        encoding="utf-8",
    )
    executable.chmod(0o755)
    monkeypatch.setenv("PATH", f"{binDir}:{tmp_path}:{os.environ.get('PATH', '')}")
