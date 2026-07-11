##############################################################################
# White-box test: confirm() default-on-empty behaviour AND accepted answers.
#
# Gap vs black-box: no CLI flag today drives confirm(), but wrappers use
# it. The invariants are: empty input → default; y/yes (any case) → True;
# anything else → False. Prompt suffix communicates the default.
##############################################################################

from __future__ import annotations

import pytest

from ansibleRunner.prompts import confirm


def testConfirmEmptyReturnsDefaultTrue() -> None:
    """Verify empty answer returns the True default."""

    assert confirm("ok?", default=True, reader=lambda _p: "") is True


def testConfirmEmptyReturnsDefaultFalse() -> None:
    """Verify empty answer returns the False default."""

    assert confirm("ok?", default=False, reader=lambda _p: "") is False


@pytest.mark.parametrize("answer", ["y", "Y", "yes", "YES", "Yes"])
def testConfirmYesAnswersAcceptedRegardlessOfCase(answer: str) -> None:
    """Verify y/yes answers are accepted regardless of case."""

    assert confirm("ok?", default=False, reader=lambda _p: answer) is True


@pytest.mark.parametrize("answer", ["n", "no", "nope", "maybe", "sure"])
def testConfirmNonYesAnswersRejected(answer: str) -> None:
    """Verify only literal y/yes count as yes; synonyms are rejected."""

    assert confirm("ok?", default=True, reader=lambda _p: answer) is False


def testConfirmSuffixReflectsDefault() -> None:
    """Verify prompt suffix communicates the default answer."""

    seen: list[str] = []

    def reader(prompt: str) -> str:
        seen.append(prompt)
        return ""

    confirm("go?", default=True, reader=reader)
    confirm("go?", default=False, reader=reader)
    assert "[Y/n]" in seen[0]
    assert "[y/N]" in seen[1]
