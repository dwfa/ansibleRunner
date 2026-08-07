##############################################################################
# AR display markup unit tests.
#
# USAGE:
#   python3 -m pytest tests/unit/testArMarkup.py
#
# WORKFLOW:
#   1. Verify AR-only style tags render safely and strip to plain text.
#
# Copyright 2026 Douglas WF Acheson (dwfa@dwfa.ca)
# Licensed under Apache License 2.0. See LICENSE.md for details.
#
# Version: 1.0
# Date: August 07, 2026
##############################################################################

from __future__ import annotations

from ansibleRunner.tui.markup import renderArMarkup, stripArMarkup


def testRenderArMarkupPreservesPlainBracketText() -> None:
    """Verify bracket-heavy Ansible output remains literal text."""

    rendered = renderArMarkup("server = [/tmp/currentRPiImage.img]")

    assert rendered.plain == "server = [/tmp/currentRPiImage.img]"


def testRenderArMarkupAppliesAllowedStyles() -> None:
    """Verify allowed AR style tags become Rich spans."""

    rendered = renderArMarkup("{green}ok{/green} plain")

    assert rendered.plain == "ok plain"
    assert rendered.spans[0].style == "green"


def testStripArMarkupRemovesAllowedTagsOnly() -> None:
    """Verify plain-text consumers drop known AR tags."""

    assert (
        stripArMarkup("{green}ok{/green} {unknown}kept{/unknown}")
        == "ok {unknown}kept{/unknown}"
    )
