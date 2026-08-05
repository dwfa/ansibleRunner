##############################################################################
# Publish workflow unit tests for ansibleRunner.
#
# USAGE:
#   python3 -m pytest tests/unit/testPublishWorkflow.py
#
# WORKFLOW:
#   1. Verify release versions are read from pyproject.toml.
#   2. Verify dirty worktrees prevent publishing.
#   3. Verify unsynced branches prevent publishing unless explicitly pushed.
#   4. Verify the publish command sequence pushes the tag and release assets.
#
# Copyright 2026 Douglas WF Acheson (dwfa@dwfa.ca)
# Licensed under Apache License 2.0. See LICENSE.md for details.
#
# Version: 1.0
# Date: August 04, 2026
##############################################################################

from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest


def testReadProjectVersionUsesPyprojectMetadata(tmp_path: Path) -> None:
    """Verify publish.py reads the release version from pyproject.toml."""

    publish = _loadPublishModule()
    pyprojectPath = tmp_path / "pyproject.toml"
    pyprojectPath.write_text(
        "\n".join(
            [
                "[project]",
                'name = "ansibleRunner"',
                'version = "1.2.3"',
            ]
        ),
        encoding="utf-8",
    )

    assert publish.readProjectVersion(tmp_path) == "1.2.3"


def testParseArgsSupportsShortMaintainerFlags() -> None:
    """Verify publish.py supports compact maintainer flag aliases."""

    publish = _loadPublishModule()

    args = publish.parseArgs(["-dr", "-sb", "-pb", "-ut"])

    assert args.dry_run is True
    assert args.skip_build is True
    assert args.push_branch is True
    assert args.reuse_tag is True
    assert args.replace_tag is False


def testPublishUiKeepsStatusMarkerNearStepText() -> None:
    """Verify publish status markers are not floated to the panel edge."""

    publish = _loadPublishModule()
    ui = publish.PublishUi(spinner=False)

    line = ui._stepLine("Validate release inputs", "", "✅")

    assert "Validate release inputs ✅" in line
    assert "Validate release inputs  ✅" not in line


def testRequireCleanWorktreeRejectsDirtyStatus(
    monkeypatch: Any,
    tmp_path: Path,
) -> None:
    """Verify uncommitted files block publishing."""

    publish = _loadPublishModule()

    def fakeRunCommand(
        command: list[str],
        cwd: Path,
        dryRun: bool = False,
        mutates: bool = False,
    ) -> subprocess.CompletedProcess[str]:
        """Return dirty git status output."""

        del command, cwd, dryRun, mutates
        return subprocess.CompletedProcess([], 0, stdout=" M README.md\n", stderr="")

    monkeypatch.setattr(publish, "runCommand", fakeRunCommand)

    with pytest.raises(SystemExit) as exc:
        publish.requireCleanWorktree(tmp_path)

    assert "dirty worktree" in str(exc.value)
    assert "README.md" in str(exc.value)


def testRequireHeadSyncedRejectsAheadBranch(
    monkeypatch: Any,
    tmp_path: Path,
) -> None:
    """Verify publish.py rejects local commits that are not on upstream."""

    publish = _loadPublishModule()

    def fakeRunCommand(
        command: list[str],
        cwd: Path,
        dryRun: bool = False,
        mutates: bool = False,
    ) -> subprocess.CompletedProcess[str]:
        """Return git state where HEAD is ahead of upstream."""

        del cwd, dryRun, mutates
        if command == ["git", "rev-parse", "HEAD"]:
            return subprocess.CompletedProcess(command, 0, stdout="local\n", stderr="")
        if command == ["git", "rev-parse", "origin/main"]:
            return subprocess.CompletedProcess(command, 0, stdout="remote\n", stderr="")
        if command == [
            "git",
            "rev-list",
            "--left-right",
            "--count",
            "HEAD...origin/main",
        ]:
            return subprocess.CompletedProcess(command, 0, stdout="1\t0\n", stderr="")
        raise AssertionError(command)

    monkeypatch.setattr(publish, "runCommand", fakeRunCommand)

    with pytest.raises(SystemExit) as exc:
        publish.requireHeadSyncedToUpstream(tmp_path, "main", "origin/main")

    assert "main has 1 local commit(s)" in str(exc.value)
    assert "--push-branch" in str(exc.value)


def testPushCurrentBranchUsesOriginBranch(
    monkeypatch: Any,
    tmp_path: Path,
) -> None:
    """Verify --push-branch pushes the current branch explicitly."""

    publish = _loadPublishModule()
    calls: list[list[str]] = []

    def fakeRunCommand(
        command: list[str],
        cwd: Path,
        dryRun: bool = False,
        mutates: bool = False,
    ) -> subprocess.CompletedProcess[str]:
        """Capture git push command."""

        del cwd, dryRun, mutates
        calls.append(command)
        return subprocess.CompletedProcess(command, 0, stdout="", stderr="")

    monkeypatch.setattr(publish, "runCommand", fakeRunCommand)
    context = publish.PublishContext(
        dryRun=False,
        projectRoot=tmp_path,
        tagName="v1.2.3",
        version="1.2.3",
    )

    publish.pushCurrentBranch(context, "main")

    assert calls == [["git", "push", "origin", "main"]]


def testPublishReleasePushesTagAndAssets(
    monkeypatch: Any,
    tmp_path: Path,
) -> None:
    """Verify publish.py builds the expected git and gh release commands."""

    publish = _loadPublishModule()
    calls: list[list[str]] = []

    def fakeRunCommand(
        command: list[str],
        cwd: Path,
        dryRun: bool = False,
        mutates: bool = False,
    ) -> subprocess.CompletedProcess[str]:
        """Capture publish commands."""

        del cwd, dryRun, mutates
        calls.append(command)
        return subprocess.CompletedProcess(command, 0, stdout="", stderr="")

    monkeypatch.setattr(publish, "runCommand", fakeRunCommand)
    monkeypatch.setattr(publish, "ghReleaseExists", lambda projectRoot, tagName: False)
    context = publish.PublishContext(
        dryRun=False,
        projectRoot=tmp_path,
        tagName="v1.2.3",
        version="1.2.3",
    )
    wheelPath = tmp_path / "dist" / "ansiblerunner-1.2.3-py3-none-any.whl"

    publish.publishRelease(context, wheelPath)

    assert calls == [
        ["git", "tag", "-a", "v1.2.3", "-m", "Release 1.2.3"],
        ["git", "push", "origin", "v1.2.3"],
        [
            "gh",
            "release",
            "create",
            "v1.2.3",
            str(tmp_path / "install.py"),
            str(wheelPath),
            "--title",
            "ansibleRunner v1.2.3",
            "--notes",
            "## ansibleRunner 1.2.3\n\n"
            "Release generated by scripts/publish.py.\n",
        ],
    ]


def testPublishReleaseReusesTagAndClobbersExistingAssets(
    monkeypatch: Any,
    tmp_path: Path,
) -> None:
    """Verify --reuse-tag skips tag creation and updates release assets."""

    publish = _loadPublishModule()
    calls: list[list[str]] = []

    def fakeRunCommand(
        command: list[str],
        cwd: Path,
        dryRun: bool = False,
        mutates: bool = False,
    ) -> subprocess.CompletedProcess[str]:
        """Capture publish commands."""

        del cwd, dryRun, mutates
        calls.append(command)
        return subprocess.CompletedProcess(command, 0, stdout="", stderr="")

    monkeypatch.setattr(publish, "runCommand", fakeRunCommand)
    monkeypatch.setattr(publish, "ghReleaseExists", lambda projectRoot, tagName: True)
    context = publish.PublishContext(
        dryRun=False,
        projectRoot=tmp_path,
        tagName="v1.2.3",
        version="1.2.3",
    )
    wheelPath = tmp_path / "dist" / "ansiblerunner-1.2.3-py3-none-any.whl"

    publish.publishRelease(context, wheelPath, reuseTag=True)

    assert calls == [
        [
            "gh",
            "release",
            "upload",
            "v1.2.3",
            str(tmp_path / "install.py"),
            str(wheelPath),
            "--clobber",
        ],
    ]


def testPublishReleaseReplacesTagAndClobbersExistingAssets(
    monkeypatch: Any,
    tmp_path: Path,
) -> None:
    """Verify --replace-tag force-moves the tag and updates release assets."""

    publish = _loadPublishModule()
    calls: list[list[str]] = []

    def fakeRunCommand(
        command: list[str],
        cwd: Path,
        dryRun: bool = False,
        mutates: bool = False,
    ) -> subprocess.CompletedProcess[str]:
        """Capture publish commands."""

        del cwd, dryRun, mutates
        calls.append(command)
        return subprocess.CompletedProcess(command, 0, stdout="", stderr="")

    monkeypatch.setattr(publish, "runCommand", fakeRunCommand)
    monkeypatch.setattr(publish, "ghReleaseExists", lambda projectRoot, tagName: True)
    context = publish.PublishContext(
        dryRun=False,
        projectRoot=tmp_path,
        tagName="v1.2.3",
        version="1.2.3",
    )
    wheelPath = tmp_path / "dist" / "ansiblerunner-1.2.3-py3-none-any.whl"

    publish.publishRelease(context, wheelPath, replaceTag=True)

    assert calls == [
        ["git", "tag", "-f", "-a", "v1.2.3", "-m", "Release 1.2.3"],
        ["git", "push", "--force", "origin", "v1.2.3"],
        [
            "gh",
            "release",
            "upload",
            "v1.2.3",
            str(tmp_path / "install.py"),
            str(wheelPath),
            "--clobber",
        ],
    ]


def testRequireExistingTagAtHeadRejectsDifferentLocalTag(
    monkeypatch: Any,
    tmp_path: Path,
) -> None:
    """Verify --reuse-tag refuses tags that do not point at HEAD."""

    publish = _loadPublishModule()

    def fakeRunCommand(
        command: list[str],
        cwd: Path,
        dryRun: bool = False,
        mutates: bool = False,
    ) -> subprocess.CompletedProcess[str]:
        """Return different object ids for HEAD and the local tag."""

        del cwd, dryRun, mutates
        if command == ["git", "rev-parse", "HEAD"]:
            return subprocess.CompletedProcess(command, 0, stdout="head\n", stderr="")
        if command == ["git", "rev-parse", "v1.2.3^{}"]:
            return subprocess.CompletedProcess(command, 0, stdout="tag\n", stderr="")
        raise AssertionError(command)

    monkeypatch.setattr(publish, "runCommand", fakeRunCommand)

    with pytest.raises(SystemExit) as exc:
        publish.requireExistingTagAtHead(tmp_path, "v1.2.3")

    assert "local tag does not point at HEAD" in str(exc.value)
    assert "--replace-tag" in str(exc.value)


def _loadPublishModule() -> Any:
    """Load scripts/publish.py as an importable test module."""

    scriptPath = Path(__file__).resolve().parents[2] / "scripts" / "publish.py"
    spec = importlib.util.spec_from_file_location("ansibleRunnerPublishScript", scriptPath)
    assert spec is not None
    assert spec.loader is not None

    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module
