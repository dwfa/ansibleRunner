##############################################################################
# White-box test: RunnerResult.progress derives status purely from returnCode.
#
# Gap vs black-box: The public runPlaybook contract only exposes returnCode
# on the result. The mapping (0 -> SUCCEEDED, non-zero -> FAILED) is an
# internal state-machine invariant that no CLI or main() call surfaces.
##############################################################################

from __future__ import annotations

from ansibleRunner.progress import RunProgress, RunStatus
from ansibleRunner.runner import RunnerResult


def testRunnerResultProgressMapsZeroToSucceeded() -> None:
    """Verify returnCode 0 maps to SUCCEEDED."""

    result = RunnerResult(command=(), returnCode=0, stdout="", stderr="")
    progress = result.progress
    assert isinstance(progress, RunProgress)
    assert progress.status is RunStatus.SUCCEEDED
    assert progress.returnCode == 0


def testRunnerResultProgressMapsNonZeroToFailed() -> None:
    """Verify every non-zero returnCode maps to FAILED."""

    for rc in (1, 2, 7, 130, 255):
        result = RunnerResult(command=(), returnCode=rc, stdout="", stderr="")
        assert result.progress.status is RunStatus.FAILED, rc
        assert result.progress.returnCode == rc
