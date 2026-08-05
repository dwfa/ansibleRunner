##############################################################################
# White-box test: runPlaybook returns a well-shaped error result when the
# playbook file is missing, WITHOUT spawning a subprocess. The empty command
# tuple is the signal "we did not exec anything."
#
# Gap vs black-box: The CLI never surfaces runPlaybook directly; wrappers
# depend on this exact-shape contract to decide whether to proceed.
##############################################################################

from __future__ import annotations

from pathlib import Path

from ansibleRunner.runner import AnsibleCommandRunner


def testRunPlaybookMissingFileReturnsNoExecMarker(tmp_path: Path) -> None:
    """Verify missing file returns empty command tuple and diagnostic log."""

    runner = AnsibleCommandRunner(tmp_path, tmp_path / "logs")
    result = runner.runPlaybook("nope.yaml", "web")
    assert result.returnCode == 1
    assert result.command == ()
    assert result.logPath is not None
    assert result.logPath.is_file()
    assert result.eventLogPath is not None
    assert result.eventLogPath.is_file()
    assert "file not found" in result.logPath.read_text(encoding="utf-8")


def testRunPlaybookMissingFileCheckedWhenNodeIsUnset(tmp_path: Path) -> None:
    """Verify missing node does not hide a missing playbook diagnostic."""

    runner = AnsibleCommandRunner(tmp_path, tmp_path / "logs")
    result = runner.runPlaybook("does-not-exist.yaml", "")
    assert "file not found" in result.stderr.lower()
    assert "no node" not in result.stderr.lower()
