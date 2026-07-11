##############################################################################
# White-box test: Chain KeyboardInterrupt at a Pause returns 130 (SIGINT
# convention). Reachable only by monkey-patching input(), because Pause
# is the sole seam that reads from stdin during runChain.
#
# Private-reach note: monkey-patching the builtin input via
# ansibleRunner.runner.input would only work if it were re-imported.
# runner.py calls the builtin directly, so we use monkeypatch on
# builtins.input — a legitimate seam for interactive prompts.
##############################################################################

from __future__ import annotations

from pathlib import Path
from typing import Any

from ansibleRunner.runner import AnsibleCommandRunner, Pause, PlaybookRun


def testChainPauseKeyboardInterruptReturns130(
    tmp_path: Path,
    monkeypatch: Any,
) -> None:
    """Verify Ctrl-C at a Pause returns SIGINT exit code 130."""

    def raiseInterrupt(_prompt: str) -> str:
        raise KeyboardInterrupt

    monkeypatch.setattr("builtins.input", raiseInterrupt)
    runner = AnsibleCommandRunner(tmp_path, tmp_path / "logs")
    rc = runner.runChain([Pause("wait")])
    assert rc == 130


def testChainProcessesPauseAndContinuesOnEnter(
    tmp_path: Path,
    monkeypatch: Any,
) -> None:
    """Verify that after a successful Pause, subsequent entries run."""

    calls: list[str] = []

    def fakeInput(_prompt: str) -> str:
        calls.append("paused")
        return ""

    monkeypatch.setattr("builtins.input", fakeInput)
    runner = AnsibleCommandRunner(tmp_path, tmp_path / "logs")
    rc = runner.runChain(
        [Pause("wait"), PlaybookRun(playbook="missing.yaml", defaultNode="")]
    )
    assert calls == ["paused"]
    assert rc == 1
