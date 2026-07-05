"""Progress models for long-running Ansible work."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class RunStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


@dataclass(frozen=True)
class RunProgress:
    status: RunStatus
    message: str = ""
    return_code: int | None = None

    @classmethod
    def pending(cls, message: str = "") -> "RunProgress":
        return cls(status=RunStatus.PENDING, message=message)

    @classmethod
    def running(cls, message: str = "") -> "RunProgress":
        return cls(status=RunStatus.RUNNING, message=message)

    @classmethod
    def finished(cls, return_code: int, message: str = "") -> "RunProgress":
        status = RunStatus.SUCCEEDED if return_code == 0 else RunStatus.FAILED
        return cls(status=status, message=message, return_code=return_code)

