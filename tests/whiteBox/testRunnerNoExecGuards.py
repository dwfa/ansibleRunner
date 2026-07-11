##############################################################################
# White-box test: runPlaybook returns a well-shaped error result when the
# playbook file is missing OR when no node can be resolved, WITHOUT
# spawning a subprocess. The empty command tuple is the signal
# "we did not exec anything."
#
# Gap vs black-box: The CLI never surfaces runPlaybook directly; wrappers
# depend on this exact-shape contract to decide whether to proceed.
##############################################################################

from __future__ import annotations

from pathlib import Path

from ansibleRunner.runner import AnsibleCommandRunner


def testRunPlaybookMissingFileReturnsNoExecMarker(tmp_path: Path) -> None:
    """Verify missing file returns empty command tuple and rc=1."""

    runner = AnsibleCommandRunner(tmp_path, tmp_path / "logs")
    result = runner.runPlaybook("nope.yaml", "web")
    assert result.returnCode == 1
    assert result.command == ()
    assert result.logPath is None


def testRunPlaybookMissingNodeReturnsNoExecMarker(tmp_path: Path) -> None:
    """Verify missing node returns empty command tuple and rc=1."""

    runner = AnsibleCommandRunner(tmp_path, tmp_path / "logs")
    result = runner.runPlaybook("anything.yaml", "")
    assert result.returnCode == 1
    assert result.command == ()
    assert result.logPath is None


def testRunPlaybookMissingNodeCheckedBeforeFileExistence(tmp_path: Path) -> None:
    """Verify node check runs before playbook file check."""

    runner = AnsibleCommandRunner(tmp_path, tmp_path / "logs")
    result = runner.runPlaybook("does-not-exist.yaml", "")
    assert "no node" in result.stderr.lower()
    assert "not found" not in result.stderr.lower()
