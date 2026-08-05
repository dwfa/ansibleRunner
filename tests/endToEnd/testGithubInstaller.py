##############################################################################
# GitHub installer end-to-end tests for ansibleRunner.
#
# USAGE:
#   python3 -m pytest tests/endToEnd/testGithubInstaller.py
#
# WORKFLOW:
#   1. Verify installer argument defaults and package spec creation.
#   2. Verify venv, pip install, and launcher commands are project-local.
#
# Copyright 2026 Douglas WF Acheson (dwfa@dwfa.ca)
# Licensed under Apache License 2.0. See LICENSE.md for details.
#
# Version: 1.0
# Date: August 03, 2026
##############################################################################

from __future__ import annotations

import importlib.util
import json
import os
import stat
import subprocess
import sys
from pathlib import Path
from typing import Any


def testPackageSpecDefaultsToLatestReleaseWheel(monkeypatch: Any) -> None:
    """Verify the installer defaults to the latest release wheel."""

    installer = _loadInstallerModule()
    monkeypatch.setattr(
        installer,
        "latestReleaseWheelUrl",
        lambda: "https://example.test/ansiblerunner-9.9.9-py3-none-any.whl",
    )
    args = installer.parseArgs([])

    assert installer.getPackageSpec(args) == (
        "ansibleRunner @ https://example.test/ansiblerunner-9.9.9-py3-none-any.whl"
    )


def testPackageSpecPrefersNewestProjectLocalWheel(tmp_path: Path) -> None:
    """Verify the newest manually downloaded release wheel is used when present."""

    installer = _loadInstallerModule()
    oldWheelPath = tmp_path / "ansiblerunner-1.0.4-py3-none-any.whl"
    oldWheelPath.write_text("wheel\n", encoding="utf-8")
    wheelPath = tmp_path / "ansiblerunner-1.0.5-py3-none-any.whl"
    wheelPath.write_text("wheel\n", encoding="utf-8")
    args = installer.parseArgs([])

    assert installer.getPackageSpec(args, tmp_path) == str(wheelPath)


def testLatestReleaseWheelUrlPrefersHighestWheelVersion(monkeypatch: Any) -> None:
    """Verify remote release selection uses wheel version, not release order."""

    installer = _loadInstallerModule()
    releases = [
        {
            "assets": [
                {
                    "name": "ansiblerunner-1.0.4-py3-none-any.whl",
                    "browser_download_url": "https://example.test/1.0.4.whl",
                }
            ]
        },
        {
            "assets": [
                {
                    "name": "ansiblerunner-1.0.10-py3-none-any.whl",
                    "browser_download_url": "https://example.test/1.0.10.whl",
                }
            ]
        },
        {
            "assets": [
                {
                    "name": "install.py",
                    "browser_download_url": "https://example.test/install.py",
                }
            ]
        },
    ]

    class FakeResponse:
        """Small context manager matching urllib response behavior."""

        def __enter__(self) -> FakeResponse:
            return self

        def __exit__(self, *args: object) -> None:
            return None

        def read(self) -> bytes:
            return json.dumps(releases).encode("utf-8")

    monkeypatch.setattr(
        installer.urllib.request,
        "urlopen",
        lambda *args, **kwargs: FakeResponse(),
    )

    assert installer.latestReleaseWheelUrl() == "https://example.test/1.0.10.whl"


def testPackageSpecCanInstallFromGit() -> None:
    """Verify the installer can still install from Git for development."""

    installer = _loadInstallerModule()
    args = installer.parseArgs(["--install-from-git"])

    assert installer.getPackageSpec(args) == (
        "ansibleRunner @ git+https://github.com/dwfa/ansibleRunner.git@main"
    )


def testPackageSpecCanBeOverridden() -> None:
    """Verify forks, branches, and local package specs can be supplied."""

    installer = _loadInstallerModule()
    args = installer.parseArgs(["--package-spec", "/tmp/ansibleRunner"])

    assert installer.getPackageSpec(args) == "/tmp/ansibleRunner"


def testInstallerUiAlignsStatusMarkerInStatusColumn() -> None:
    """Verify installer status markers are aligned away from step text."""

    installer = _loadInstallerModule()
    ui = installer.InstallerUi(Path("/tmp/install.log"))

    line = ui._stepLine("Install ansibleRunner", "", "✅")
    titleEnd = line.index("Install ansibleRunner") + len("Install ansibleRunner")
    markerIndex = line.index("✅")

    assert line.rstrip().endswith("✅")
    assert markerIndex - titleEnd > 5


def testEnsureVenvCreatesMissingEnvironment(monkeypatch: Any, tmp_path: Path) -> None:
    """Verify the installer creates a missing project virtual environment."""

    installer = _loadInstallerModule()
    calls: list[list[str]] = []

    def fakeRun(command: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        """Capture subprocess calls."""

        calls.append(command)
        return subprocess.CompletedProcess(command, 0)

    monkeypatch.setattr(installer.subprocess, "run", fakeRun)

    created = installer.ensureVenv(
        tmp_path / ".venv",
        "python3",
        tmp_path / "install.log",
    )

    assert created is True
    assert calls == [["python3", "-m", "venv", str(tmp_path / ".venv")]]


def testEnsureVenvReusesExistingEnvironment(
    monkeypatch: Any, tmp_path: Path
) -> None:
    """Verify existing virtual environments are reused."""

    installer = _loadInstallerModule()
    venvPython = tmp_path / ".venv" / "bin" / "python"
    venvPython.parent.mkdir(parents=True)
    venvPython.write_text("python\n", encoding="utf-8")
    calls: list[list[str]] = []

    monkeypatch.setattr(
        installer.subprocess,
        "run",
        lambda command, **kwargs: calls.append(command),
    )

    created = installer.ensureVenv(
        tmp_path / ".venv",
        "python3",
        tmp_path / "install.log",
    )

    assert created is False
    assert calls == []


def testInstallPackageUsesVenvPip(monkeypatch: Any, tmp_path: Path) -> None:
    """Verify pip installation runs inside the project virtual environment."""

    installer = _loadInstallerModule()
    calls: list[list[str]] = []

    def fakeRun(command: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        """Capture subprocess calls."""

        calls.append(command)
        return subprocess.CompletedProcess(command, 0)

    monkeypatch.setattr(installer.subprocess, "run", fakeRun)

    installer.installPackage(
        Path("/project/.venv/bin/python"),
        "ansibleRunner @ https://example.test/ansiblerunner-9.9.9-py3-none-any.whl",
        tmp_path / "logs" / "install.log",
    )

    assert calls == [
        [
            "/project/.venv/bin/python",
            "-m",
            "pip",
            "install",
            "--upgrade",
            "--disable-pip-version-check",
            "ansibleRunner @ https://example.test/ansiblerunner-9.9.9-py3-none-any.whl",
        ]
    ]


def testInstallLogPathUsesProjectLogs(tmp_path: Path) -> None:
    """Verify installer logs are written under project logs."""

    installer = _loadInstallerModule()

    logPath = installer.getInstallLogPath(tmp_path)

    assert logPath.parent == tmp_path / "logs"
    assert logPath.name.startswith("ansibleRunner-install-")
    assert logPath.suffix == ".log"


def testWriteLauncherRunsInstalledPackage(tmp_path: Path) -> None:
    """Verify the generated launcher delegates to the installed package."""

    installer = _loadInstallerModule()
    launcherPath = tmp_path / "ar.py"

    installer.writeLauncher(launcherPath, tmp_path / ".venv")

    launcherText = launcherPath.read_text(encoding="utf-8")
    assert "PROJECT_ROOT / '.venv'" in launcherText
    assert 'RUNNER = VENV_DIR / "bin" / "ansibleRunner"' in launcherText
    assert '"--project-root",' in launcherText
    assert os.access(launcherPath, os.X_OK)
    assert launcherPath.stat().st_mode & stat.S_IXUSR


def testInstallerSyntaxIsValid() -> None:
    """Verify install.py is executable Python source."""

    installerPath = Path(__file__).resolve().parents[2] / "install.py"

    result = subprocess.run(
        [sys.executable, "-m", "py_compile", str(installerPath)],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr


def _loadInstallerModule() -> Any:
    """Load install.py as an importable test module."""

    installerPath = Path(__file__).resolve().parents[2] / "install.py"
    spec = importlib.util.spec_from_file_location(
        "ansibleRunnerInstaller",
        installerPath,
    )
    assert spec is not None
    assert spec.loader is not None

    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module
