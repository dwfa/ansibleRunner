##############################################################################
# White-box test: RunProgress.finished — status is a function of returnCode
# alone. This is the core lifecycle transition that RunnerResult.progress
# relies on.
#
# Gap vs black-box: no CLI path emits progress objects.
##############################################################################

from __future__ import annotations

import pytest

from ansibleRunner.progress import RunProgress, RunStatus


def testFinishedZeroIsSucceeded() -> None:
    """Verify finished(0) is SUCCEEDED and carries the message."""

    p = RunProgress.finished(0, "done")
    assert p.status is RunStatus.SUCCEEDED
    assert p.returnCode == 0
    assert p.message == "done"


def testFinishedNonZeroIsFailed() -> None:
    """Verify finished(non-zero) is FAILED and carries the return code."""

    p = RunProgress.finished(2)
    assert p.status is RunStatus.FAILED
    assert p.returnCode == 2


def testRunningAndPendingCarryStatus() -> None:
    """Verify pending()/running() constructors set the expected status."""

    assert RunProgress.pending().status is RunStatus.PENDING
    assert RunProgress.running().status is RunStatus.RUNNING


def testRunProgressIsFrozen() -> None:
    """Verify progress snapshots are immutable; callers cache them."""

    p = RunProgress.finished(0)
    with pytest.raises(Exception):
        p.status = RunStatus.FAILED  # type: ignore[misc]
