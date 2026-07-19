##############################################################################
# White-box test: _resolveLogDir precedence — explicit arg > LOG_DIR env >
# RuntimeDefaults.
#
# Gap vs black-box: black-box tests only exercise the explicit-arg branch
# via the constructor. The env-variable fallback is documented behavior
# but reachable only by constructing the runner directly. The narrowest
# public seam is the constructor + reading .logDir.
##############################################################################

from __future__ import annotations

from pathlib import Path
from typing import Any

from ansibleRunner.runner import AnsibleCommandRunner


def testLogDirEnvVarUsedWhenNoExplicitArg(tmp_path: Path, monkeypatch: Any) -> None:
    """Verify LOG_DIR env is used when no explicit logDir is supplied."""

    envDir = tmp_path / "from_env"
    monkeypatch.setenv("LOG_DIR", str(envDir))
    runner = AnsibleCommandRunner(tmp_path)
    assert runner.logDir == envDir


def testLogDirExplicitArgWinsOverEnv(tmp_path: Path, monkeypatch: Any) -> None:
    """Verify explicit logDir argument overrides LOG_DIR env."""

    monkeypatch.setenv("LOG_DIR", str(tmp_path / "from_env"))
    explicit = tmp_path / "explicit"
    runner = AnsibleCommandRunner(tmp_path, explicit)
    assert runner.logDir == explicit


def testLogDirFallsBackToProjectDefault(tmp_path: Path, monkeypatch: Any) -> None:
    """Verify fallback is RuntimeDefaults(projectRoot).logDir."""

    monkeypatch.delenv("LOG_DIR", raising=False)
    runner = AnsibleCommandRunner(tmp_path)
    assert runner.logDir == tmp_path.resolve() / "logs"
