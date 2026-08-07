##############################################################################
# AR display markup helpers.
#
# USAGE:
#   renderArMarkup("{green}ok{/green}")
#   stripArMarkup("{green}ok{/green}")
#
# Copyright 2026 Douglas WF Acheson (dwfa@dwfa.ca)
# Licensed under Apache License 2.0. See LICENSE.md for details.
#
# Version: 1.0
# Date: August 07, 2026
##############################################################################

"""Small, safe markup helpers for AR-only display styling."""

from __future__ import annotations

import re

from rich.text import Text


AR_STYLE_TAG_PATTERN = re.compile(
    r"\{(/?)(bold|blue|cyan|dim|green|magenta|red|white|yellow)\}"
)


def renderArMarkup(value: str, baseStyle: str = "") -> Text:
    """Render safe AR markup tags into a Rich Text object.

    Args:
        baseStyle: Style applied to text outside explicit AR tags.
        value: Text that may contain AR tags such as ``{green}``.

    Returns:
        Rich text with known AR tags styled and unknown text preserved.
    """

    text = Text()
    styleStack: list[str] = []
    offset = 0
    for match in AR_STYLE_TAG_PATTERN.finditer(value):
        if match.start() > offset:
            text.append(value[offset : match.start()], style=_combinedStyle(baseStyle, styleStack))
        closing, style = match.groups()
        if closing:
            if style in styleStack:
                stackIndex = len(styleStack) - 1 - styleStack[::-1].index(style)
                del styleStack[stackIndex:]
            else:
                text.append(match.group(0), style=_combinedStyle(baseStyle, styleStack))
        else:
            styleStack.append(style)
        offset = match.end()
    if offset < len(value):
        text.append(value[offset:], style=_combinedStyle(baseStyle, styleStack))
    return text


def stripArMarkup(value: str) -> str:
    """Remove known AR markup tags from text.

    Args:
        value: Text that may contain AR markup tags.

    Returns:
        Plain text with AR tags removed.
    """

    return AR_STYLE_TAG_PATTERN.sub("", value)


def _combinedStyle(baseStyle: str, styleStack: list[str]) -> str:
    """Return the active style string for a rendered span."""

    return " ".join([style for style in (baseStyle, *styleStack) if style])
