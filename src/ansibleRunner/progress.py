##############################################################################
# Progress models for long-running Ansible operations.
#
# USAGE:
#   RunProgress.running("message")
#   RunProgress.finished(returnCode)
#
# OUTPUT VARIABLES:
#   - RunProgress: Immutable progress snapshot.
#   - RunStatus: Supported lifecycle states.
#
# Copyright 2026 Douglas WF Acheson (dwfa@dwfa.ca)
# Licensed under Apache License 2.0. See LICENSE.md for details.
#
# Version: 1.0
# Date: July 05, 2026
##############################################################################

"""Progress models for long-running Ansible work."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class RunStatus(str, Enum):
    """Lifecycle states for long-running Ansible work."""

    PENDING = "pending"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


@dataclass(frozen=True)
class RunProgress:
    """Immutable progress snapshot for a runner operation.

    Args:
        status: Current runner lifecycle state.
        message: Optional human-readable progress message.
        returnCode: Optional process return code when finished.
    """

    status: RunStatus
    message: str = ""
    returnCode: int | None = None

    @classmethod
    def pending(cls, message: str = "") -> "RunProgress":
        """Create a pending progress snapshot.

        Args:
            message: Optional human-readable progress message.

        Returns:
            Pending progress snapshot.
        """

        return cls(status=RunStatus.PENDING, message=message)

    @classmethod
    def running(cls, message: str = "") -> "RunProgress":
        """Create a running progress snapshot.

        Args:
            message: Optional human-readable progress message.

        Returns:
            Running progress snapshot.
        """

        return cls(status=RunStatus.RUNNING, message=message)

    @classmethod
    def finished(cls, returnCode: int, message: str = "") -> "RunProgress":
        """Create a finished progress snapshot from a process return code.

        Args:
            returnCode: Completed process return code.
            message: Optional human-readable progress message.

        Returns:
            Succeeded or failed progress snapshot.
        """

        status = RunStatus.SUCCEEDED if returnCode == 0 else RunStatus.FAILED
        return cls(status=status, message=message, returnCode=returnCode)
