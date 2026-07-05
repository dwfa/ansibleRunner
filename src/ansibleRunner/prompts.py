"""Prompt handling primitives."""

from __future__ import annotations

from collections.abc import Callable


InputReader = Callable[[str], str]


def confirm(prompt: str, default: bool = False, reader: InputReader = input) -> bool:
    suffix = "Y/n" if default else "y/N"
    answer = reader(f"{prompt} [{suffix}] ").strip().lower()
    if not answer:
        return default
    return answer in {"y", "yes"}

