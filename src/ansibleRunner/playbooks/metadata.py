##############################################################################
# Playbook metadata parsing helpers.
#
# USAGE:
#   parseTitle(path)
#
# Copyright 2026 Douglas WF Acheson (dwfa@dwfa.ca)
# Licensed under Apache License 2.0. See LICENSE.md for details.
#
# Version: 1.0
# Date: July 11, 2026
##############################################################################

"""Playbook metadata parsing helpers."""

from __future__ import annotations

from pathlib import Path


HEADER_SCAN_LINES = 30


def parseTitle(path: Path) -> str:
    """Parse a display title from a playbook header.

    Args:
        path: Playbook path to inspect.

    Returns:
        First meaningful comment line from the playbook header, or a fallback
        marker when no title can be parsed.
    """

    try:
        lines = path.read_text(encoding="utf-8").splitlines()[:HEADER_SCAN_LINES]
    except (OSError, UnicodeDecodeError):
        return "(unreadable)"

    for rawLine in lines:
        strippedLine = rawLine.strip()
        if not strippedLine or strippedLine.startswith("###"):
            continue
        if strippedLine.startswith("# ") and len(strippedLine) > 2:
            return strippedLine[2:].strip()
    return "(no title)"
