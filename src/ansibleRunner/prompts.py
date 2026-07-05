##############################################################################
# Prompt handling primitives for interactive workflows.
#
# USAGE:
#   confirm("Continue?", default=False)
#
# OUTPUT VARIABLES:
#   - confirm: Boolean confirmation helper.
#
# Copyright 2026 Douglas WF Acheson (dwfa@dwfa.ca)
# Licensed under Apache License 2.0. See LICENSE.md for details.
#
# Version: 1.0
# Date: July 05, 2026
##############################################################################

"""Prompt handling primitives."""

from __future__ import annotations

from collections.abc import Callable


InputReader = Callable[[str], str]


def confirm(prompt: str, default: bool = False, reader: InputReader = input) -> bool:
    """Ask a yes/no confirmation question.

    Args:
        prompt: Prompt text shown before the choice suffix.
        default: Value returned when the user enters no answer.
        reader: Input function used to read the answer.

    Returns:
        True when the answer is yes, otherwise False.
    """

    suffix = "Y/n" if default else "y/N"
    answer = reader(f"{prompt} [{suffix}] ").strip().lower()
    if not answer:
        return default
    return answer in {"y", "yes"}
