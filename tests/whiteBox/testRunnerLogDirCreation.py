##############################################################################
# White-box test: _execAndTee creates the log directory on demand.
#
# Gap vs black-box: existing runner test pre-creates a `logs` path via the
# runner constructor argument, but never asserts that a *non-existent*
# nested log dir is created lazily. That's an explicit mkdir(parents=True,
# exist_ok=True) invariant.
##############################################################################

from __future__ import annotations

from pathlib import Path
from typing import Any

from ansibleRunner.runner import AnsibleCommandRunner


def testRunPlaybookCreatesMissingLogDirectory(
    tmp_path: Path,
    monkeypatch: Any,
) -> None:
    """Verify runPlaybook creates a nested log directory that does not exist."""

    _writeFakeAnsible(tmp_path, monkeypatch, exitCode=0)
    playbook = tmp_path / "pb" / "site.yaml"
    playbook.parent.mkdir()
    playbook.write_text("---\n", encoding="utf-8")

    nestedLogDir = tmp_path / "does" / "not" / "yet" / "exist"
    assert not nestedLogDir.exists()

    runner = AnsibleCommandRunner(tmp_path, nestedLogDir)
    result = runner.runPlaybook("pb/site.yaml", "web")

    assert result.returnCode == 0
    assert result.logPath is not None
    assert result.logPath.is_file()
    assert nestedLogDir.is_dir()


def _writeFakeAnsible(tmp_path: Path, monkeypatch: Any, exitCode: int) -> None:
    """Write a fake ansible-playbook executable into a temporary PATH."""

    binDir = tmp_path / "bin"
    binDir.mkdir()
    executable = binDir / "ansible-playbook"
    executable.write_text(
        "#!/bin/sh\n"
        "echo running\n"
        f"exit {exitCode}\n",
        encoding="utf-8",
    )
    executable.chmod(0o755)
    monkeypatch.setenv("PATH", f"{binDir}:{tmp_path}")
