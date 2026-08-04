##############################################################################
# White-box test: parseOptions and buildPlaybookCommand preserve a fixed
# test-only flag ordering: --check, --syntax-check, --list-tasks, before
# --extra-vars, before caller extraArgs, before the playbook path.
#
# Gap vs black-box: Existing tests exercise one combination. The ordering
# invariant across arbitrary subsets — including only some flags — is what
# downstream wrappers depend on, and is not otherwise asserted.
##############################################################################

from __future__ import annotations

from pathlib import Path

from ansibleRunner.runner import AnsibleCommandRunner


def testTestOnlyFlagOrderingWithSubset() -> None:
    """Verify --syntax-check precedes --list-tasks when --check is absent."""

    options = AnsibleCommandRunner.parseOptions(["-s", "-t"])
    assert options.testOnly == ("--syntax-check", "--list-tasks")


def testTestOnlyFlagOrderingIndependentOfArgvOrder() -> None:
    """Verify testOnly order is fixed by parser, not argv order."""

    a = AnsibleCommandRunner.parseOptions(["-t", "-c", "-s"])
    b = AnsibleCommandRunner.parseOptions(["-c", "-s", "-t"])
    assert a.testOnly == b.testOnly == (
        "--check", "--syntax-check", "--list-tasks",
    )


def testBuildPlaybookCommandOrdering(tmp_path: Path) -> None:
    """Verify ordering: prog, testOnly, --extra-vars, extraArgs, playbook."""

    runner = AnsibleCommandRunner(tmp_path, tmp_path / "logs")
    options = AnsibleCommandRunner.parseOptions(["-c", "--", "--limit", "one"])
    command = runner.buildPlaybookCommand("p.yml", "web", options)
    assert command[0] == "ansible-playbook"
    assert command[-1] == "p.yml"
    extraIdx = command.index("--extra-vars")
    for flag in options.testOnly:
        assert command.index(flag) < extraIdx
    assert command.index("--limit") > extraIdx + 1
