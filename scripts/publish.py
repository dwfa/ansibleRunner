#!/usr/bin/env python3
##############################################################################
# Publish an ansibleRunner GitHub release.
#
# USAGE:
#   ./scripts/publish.py
#   python3 scripts/publish.py
#   python3 scripts/publish.py --dry-run
#
# OUTPUT VARIABLES:
#   - Git tag: v<pyproject version>
#   - GitHub release assets:
#       - install.py
#       - dist/ansiblerunner-<version>-py3-none-any.whl
#
# EXIT CODES:
#   - 0: Release was published successfully.
#   - 1: Project validation, git validation, build, or publish failed.
#   - 130: Publish was interrupted by Ctrl-C.
#
# WORKFLOW:
#   1. Validate that the script is running from an ansibleRunner source tree.
#   2. Read the package version from pyproject.toml.
#   3. Require a clean git worktree.
#   4. Require local HEAD to be synced to the branch upstream, or explicitly
#      push the branch with --push-branch.
#   5. Verify the release tag does not already exist locally or remotely.
#   6. Run scripts/build.py to test and build the release wheel.
#   7. Create and push the annotated release tag.
#   8. Create the GitHub release with install.py and the wheel attached.
#
# NOTES:
#   - This script publishes the version already declared in pyproject.toml.
#   - Use --dry-run to inspect the exact release steps without changing git or
#     GitHub.
#   - GitHub publishing requires the gh CLI to be installed and authenticated.
#
# Copyright 2026 Douglas WF Acheson (dwfa@dwfa.ca)
# Licensed under Apache License 2.0. See LICENSE.md for details.
#
# Version: 1.0
# Date: August 04, 2026
##############################################################################

from __future__ import annotations

import argparse
import re
import shutil
import subprocess
import sys
import tomllib
from dataclasses import dataclass
from pathlib import Path


PROJECT_NAME = "ansibleRunner"
RELEASE_REMOTE = "origin"
TAG_PREFIX = "v"


@dataclass(frozen=True)
class PublishContext:
    """Runtime values for a publish operation.

    Args:
        dryRun: Whether mutating commands should be printed instead of run.
        projectRoot: Project root containing pyproject.toml.
        tagName: Git release tag name.
        version: Package version being published.
    """

    dryRun: bool
    projectRoot: Path
    tagName: str
    version: str


def parseArgs(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse command-line arguments for the release publisher.

    Args:
        argv: Optional argument list. Uses process arguments when omitted.

    Returns:
        Parsed command-line namespace.
    """

    parser = argparse.ArgumentParser(
        description="Build and publish an ansibleRunner GitHub release.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print release steps without changing git or GitHub.",
    )
    parser.add_argument(
        "--skip-build",
        action="store_true",
        help="Use an existing dist wheel instead of running scripts/build.py.",
    )
    parser.add_argument(
        "--push-branch",
        action="store_true",
        help="Push the current branch to origin before tagging the release.",
    )
    tagMode = parser.add_mutually_exclusive_group()
    tagMode.add_argument(
        "--reuse-tag",
        action="store_true",
        help=(
            "Reuse an existing local/remote tag that already points at HEAD, "
            "and clobber release assets."
        ),
    )
    tagMode.add_argument(
        "--replace-tag",
        action="store_true",
        help=(
            "Move an existing local/remote tag to HEAD, force-push it, and "
            "clobber release assets."
        ),
    )
    return parser.parse_args(argv)


def runCommand(
    command: list[str],
    cwd: Path,
    dryRun: bool = False,
    mutates: bool = False,
) -> subprocess.CompletedProcess[str]:
    """Run or display a command.

    Args:
        command: Command and arguments to run.
        cwd: Working directory.
        dryRun: Whether mutating commands should be printed instead of run.
        mutates: Whether the command changes git, files, or GitHub state.

    Returns:
        Completed process result.

    Raises:
        SystemExit: When the command exits non-zero.
    """

    printableCommand = " ".join(command)
    if dryRun and mutates:
        print(f"DRY RUN: {printableCommand}")
        return subprocess.CompletedProcess(command, 0, stdout="", stderr="")

    result = subprocess.run(
        command,
        capture_output=True,
        check=False,
        cwd=cwd,
        text=True,
    )
    if result.returncode != 0:
        if result.stdout:
            print(result.stdout.rstrip())
        if result.stderr:
            print(result.stderr.rstrip(), file=sys.stderr)
        raise SystemExit(result.returncode)
    return result


def requireProjectRoot(projectRoot: Path) -> None:
    """Validate that the publisher is running from the expected source tree.

    Args:
        projectRoot: Project root containing pyproject.toml.

    Raises:
        SystemExit: When required project files are missing.
    """

    requiredPaths = [
        projectRoot / "pyproject.toml",
        projectRoot / "install.py",
        projectRoot / "scripts" / "build.py",
        projectRoot / "src" / PROJECT_NAME,
    ]
    missingPaths = [path for path in requiredPaths if not path.exists()]
    if not missingPaths:
        return

    missingText = "\n".join(f"  - {path}" for path in missingPaths)
    raise SystemExit(
        "Cannot publish because this does not look like the "
        f"{PROJECT_NAME} project root.\nMissing:\n{missingText}"
    )


def requireTool(toolName: str) -> None:
    """Require an external command-line tool to be available.

    Args:
        toolName: Command name to look up on PATH.

    Raises:
        SystemExit: When the command cannot be found.
    """

    if shutil.which(toolName):
        return

    raise SystemExit(f"Cannot publish because required tool is missing: {toolName}")


def readProjectVersion(projectRoot: Path) -> str:
    """Read the package version from pyproject.toml.

    Args:
        projectRoot: Project root containing pyproject.toml.

    Returns:
        Package version string.

    Raises:
        SystemExit: When version metadata is missing or invalid.
    """

    pyprojectPath = projectRoot / "pyproject.toml"
    metadata = tomllib.loads(pyprojectPath.read_text(encoding="utf-8"))
    project = metadata.get("project")
    if not isinstance(project, dict):
        raise SystemExit("Cannot publish because pyproject.toml has no [project].")

    version = project.get("version")
    if not isinstance(version, str) or not version:
        raise SystemExit("Cannot publish because pyproject.toml has no project.version.")

    if not re.fullmatch(r"\d+\.\d+\.\d+(?:[A-Za-z0-9_.-]+)?", version):
        raise SystemExit(f"Cannot publish invalid package version: {version}")

    return version


def requireCleanWorktree(projectRoot: Path) -> None:
    """Require a clean git worktree before publishing.

    Args:
        projectRoot: Project root containing the git repository.

    Raises:
        SystemExit: When uncommitted or untracked files are present.
    """

    result = runCommand(
        ["git", "status", "--porcelain"],
        projectRoot,
    )
    if not result.stdout.strip():
        return

    raise SystemExit(
        "Cannot publish with a dirty worktree. Commit or remove these changes first:\n"
        f"{result.stdout.rstrip()}"
    )


def getCurrentBranch(projectRoot: Path) -> str:
    """Return the current checked-out git branch.

    Args:
        projectRoot: Project root containing the git repository.

    Returns:
        Current branch name.

    Raises:
        SystemExit: When the repository is detached.
    """

    result = runCommand(
        ["git", "branch", "--show-current"],
        projectRoot,
    )
    branchName = result.stdout.strip()
    if branchName:
        return branchName

    raise SystemExit("Cannot publish from a detached HEAD.")


def getUpstreamBranch(projectRoot: Path) -> str:
    """Return the configured upstream branch for the current branch.

    Args:
        projectRoot: Project root containing the git repository.

    Returns:
        Upstream branch name such as ``origin/main``.

    Raises:
        SystemExit: When no upstream branch is configured.
    """

    result = subprocess.run(
        ["git", "rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{u}"],
        capture_output=True,
        check=False,
        cwd=projectRoot,
        text=True,
    )
    if result.returncode == 0 and result.stdout.strip():
        return result.stdout.strip()

    raise SystemExit(
        "Cannot publish because the current branch has no upstream. "
        "Set one with git push -u origin <branch>."
    )


def requireHeadSyncedToUpstream(
    projectRoot: Path,
    branchName: str,
    upstreamBranch: str,
) -> None:
    """Require local HEAD to match its upstream before publishing.

    Args:
        projectRoot: Project root containing the git repository.
        branchName: Current local branch name.
        upstreamBranch: Upstream branch name.

    Raises:
        SystemExit: When local and upstream commits differ.
    """

    head = runCommand(["git", "rev-parse", "HEAD"], projectRoot).stdout.strip()
    upstreamHead = runCommand(
        ["git", "rev-parse", upstreamBranch],
        projectRoot,
    ).stdout.strip()
    if head == upstreamHead:
        return

    counts = runCommand(
        ["git", "rev-list", "--left-right", "--count", f"HEAD...{upstreamBranch}"],
        projectRoot,
    ).stdout.split()
    aheadCount = int(counts[0]) if len(counts) >= 1 else 0
    behindCount = int(counts[1]) if len(counts) >= 2 else 0
    if aheadCount and not behindCount:
        raise SystemExit(
            f"Cannot publish because {branchName} has {aheadCount} local "
            f"commit(s) not on {upstreamBranch}. Run git push origin "
            f"{branchName}, or rerun publish with --push-branch."
        )
    if behindCount and not aheadCount:
        raise SystemExit(
            f"Cannot publish because {branchName} is behind {upstreamBranch} "
            f"by {behindCount} commit(s). Pull/rebase before publishing."
        )

    raise SystemExit(
        f"Cannot publish because {branchName} and {upstreamBranch} have "
        f"diverged ({aheadCount} ahead, {behindCount} behind). Resolve the "
        "branch state before publishing."
    )


def pushCurrentBranch(context: PublishContext, branchName: str) -> None:
    """Push the current branch to origin.

    Args:
        context: Publish context.
        branchName: Current local branch name.
    """

    runCommand(
        ["git", "push", RELEASE_REMOTE, branchName],
        context.projectRoot,
        dryRun=context.dryRun,
        mutates=True,
    )


def requireTagAvailable(projectRoot: Path, tagName: str) -> None:
    """Require that a release tag is not already present locally or remotely.

    Args:
        projectRoot: Project root containing the git repository.
        tagName: Release tag to check.

    Raises:
        SystemExit: When the tag already exists.
    """

    localResult = runCommand(
        ["git", "tag", "--list", tagName],
        projectRoot,
    )
    if localResult.stdout.strip():
        raise SystemExit(f"Cannot publish because local tag already exists: {tagName}")

    remoteResult = runCommand(
        ["git", "ls-remote", "--tags", RELEASE_REMOTE, tagName],
        projectRoot,
    )
    if remoteResult.stdout.strip():
        raise SystemExit(f"Cannot publish because remote tag already exists: {tagName}")


def revParse(projectRoot: Path, ref: str) -> str:
    """Resolve a git ref to an object id.

    Args:
        projectRoot: Project root containing the git repository.
        ref: Git ref expression to resolve.

    Returns:
        Resolved object id.
    """

    return runCommand(["git", "rev-parse", ref], projectRoot).stdout.strip()


def remoteTagObject(projectRoot: Path, tagName: str) -> str:
    """Return the remote tag target object id when it exists.

    Args:
        projectRoot: Project root containing the git repository.
        tagName: Tag to resolve on the release remote.

    Returns:
        Remote tag target object id, or an empty string when missing.
    """

    peeledResult = runCommand(
        ["git", "ls-remote", "--tags", RELEASE_REMOTE, f"{tagName}^{{}}"],
        projectRoot,
    )
    if peeledResult.stdout.strip():
        return peeledResult.stdout.split()[0]

    tagResult = runCommand(
        ["git", "ls-remote", "--tags", RELEASE_REMOTE, tagName],
        projectRoot,
    )
    if tagResult.stdout.strip():
        return tagResult.stdout.split()[0]
    return ""


def requireExistingTagAtHead(projectRoot: Path, tagName: str) -> None:
    """Require existing local and remote tags to point at HEAD.

    Args:
        projectRoot: Project root containing the git repository.
        tagName: Tag expected to point at HEAD.

    Raises:
        SystemExit: When either tag is missing or points elsewhere.
    """

    head = revParse(projectRoot, "HEAD")
    localTag = revParse(projectRoot, f"{tagName}^{{}}")
    if localTag != head:
        raise SystemExit(
            f"Cannot reuse {tagName} because the local tag does not point at HEAD. "
            "Use --replace-tag to move it."
        )

    remoteTag = remoteTagObject(projectRoot, tagName)
    if not remoteTag:
        raise SystemExit(
            f"Cannot reuse {tagName} because the remote tag does not exist. "
            "Run without --reuse-tag to create it."
        )
    if remoteTag != head:
        raise SystemExit(
            f"Cannot reuse {tagName} because the remote tag does not point at HEAD. "
            "Use --replace-tag to move it."
        )


def ghReleaseExists(projectRoot: Path, tagName: str) -> bool:
    """Return whether a GitHub release already exists for a tag."""

    result = subprocess.run(
        ["gh", "release", "view", tagName],
        capture_output=True,
        check=False,
        cwd=projectRoot,
        text=True,
    )
    return result.returncode == 0


def requireGhReleaseAvailable(projectRoot: Path, tagName: str) -> None:
    """Require that a GitHub release does not already exist.

    Args:
        projectRoot: Project root containing the git repository.
        tagName: Release tag to check.

    Raises:
        SystemExit: When the release exists or gh fails unexpectedly.
    """

    if ghReleaseExists(projectRoot, tagName):
        raise SystemExit(f"Cannot publish because GitHub release already exists: {tagName}")


def getExpectedWheelPath(projectRoot: Path, version: str) -> Path:
    """Return the expected wheel path for a release version.

    Args:
        projectRoot: Project root containing dist.
        version: Package version.

    Returns:
        Expected wheel path.
    """

    return projectRoot / "dist" / f"ansiblerunner-{version}-py3-none-any.whl"


def requireWheel(projectRoot: Path, version: str) -> Path:
    """Require the expected release wheel to exist.

    Args:
        projectRoot: Project root containing dist.
        version: Package version.

    Returns:
        Existing wheel path.

    Raises:
        SystemExit: When the wheel is missing.
    """

    wheelPath = getExpectedWheelPath(projectRoot, version)
    if wheelPath.exists():
        return wheelPath

    raise SystemExit(
        "Cannot publish because the expected wheel does not exist:\n"
        f"  {wheelPath}"
    )


def buildWheel(context: PublishContext, skipBuild: bool) -> Path:
    """Build or locate the release wheel.

    Args:
        context: Publish context.
        skipBuild: Whether to reuse an existing wheel.

    Returns:
        Release wheel path.
    """

    if skipBuild:
        return requireWheel(context.projectRoot, context.version)

    runCommand(
        [sys.executable, "scripts/build.py", "--no-spinner"],
        context.projectRoot,
        dryRun=context.dryRun,
        mutates=True,
    )
    if context.dryRun:
        return getExpectedWheelPath(context.projectRoot, context.version)
    return requireWheel(context.projectRoot, context.version)


def publishRelease(
    context: PublishContext,
    wheelPath: Path,
    reuseTag: bool = False,
    replaceTag: bool = False,
) -> None:
    """Publish the git tag and GitHub release.

    Args:
        context: Publish context.
        wheelPath: Wheel asset to attach to the release.
        reuseTag: Whether an existing HEAD tag should be reused.
        replaceTag: Whether an existing tag should be moved to HEAD.
    """

    releaseNotes = (
        f"## {PROJECT_NAME} {context.version}\n\n"
        "Release generated by scripts/publish.py.\n"
    )
    if replaceTag:
        runCommand(
            [
                "git",
                "tag",
                "-f",
                "-a",
                context.tagName,
                "-m",
                f"Release {context.version}",
            ],
            context.projectRoot,
            dryRun=context.dryRun,
            mutates=True,
        )
        runCommand(
            ["git", "push", "--force", RELEASE_REMOTE, context.tagName],
            context.projectRoot,
            dryRun=context.dryRun,
            mutates=True,
        )
    elif not reuseTag:
        runCommand(
            ["git", "tag", "-a", context.tagName, "-m", f"Release {context.version}"],
            context.projectRoot,
            dryRun=context.dryRun,
            mutates=True,
        )
        runCommand(
            ["git", "push", RELEASE_REMOTE, context.tagName],
            context.projectRoot,
            dryRun=context.dryRun,
            mutates=True,
        )

    assets = [str(context.projectRoot / "install.py"), str(wheelPath)]
    if ghReleaseExists(context.projectRoot, context.tagName):
        runCommand(
            [
                "gh",
                "release",
                "upload",
                context.tagName,
                *assets,
                "--clobber",
            ],
            context.projectRoot,
            dryRun=context.dryRun,
            mutates=True,
        )
        return

    runCommand(
        [
            "gh",
            "release",
            "create",
            context.tagName,
            *assets,
            "--title",
            f"{PROJECT_NAME} {context.tagName}",
            "--notes",
            releaseNotes,
        ],
        context.projectRoot,
        dryRun=context.dryRun,
        mutates=True,
    )


def main(argv: list[str] | None = None) -> int:
    """Run the release publisher.

    Args:
        argv: Optional argument list. Uses process arguments when omitted.

    Returns:
        Process exit code.
    """

    args = parseArgs(argv)
    projectRoot = Path(__file__).resolve().parent.parent

    try:
        requireProjectRoot(projectRoot)
        requireTool("git")
        requireTool("gh")
        version = readProjectVersion(projectRoot)
        tagName = f"{TAG_PREFIX}{version}"
        requireCleanWorktree(projectRoot)
        branchName = getCurrentBranch(projectRoot)
        upstreamBranch = getUpstreamBranch(projectRoot)

        context = PublishContext(
            dryRun=args.dry_run,
            projectRoot=projectRoot,
            tagName=tagName,
            version=version,
        )

        print(f"Publishing {PROJECT_NAME} {version}")
        if args.push_branch:
            pushCurrentBranch(context, branchName)
            if not args.dry_run:
                requireHeadSyncedToUpstream(projectRoot, branchName, upstreamBranch)
        else:
            requireHeadSyncedToUpstream(projectRoot, branchName, upstreamBranch)
        if args.reuse_tag:
            requireExistingTagAtHead(projectRoot, tagName)
        elif not args.replace_tag:
            requireTagAvailable(projectRoot, tagName)
            requireGhReleaseAvailable(projectRoot, tagName)
        wheelPath = buildWheel(context, args.skip_build)
        print(f"Wheel: {wheelPath}")
        publishRelease(
            context,
            wheelPath,
            reuseTag=args.reuse_tag,
            replaceTag=args.replace_tag,
        )
        print(f"Published {PROJECT_NAME} {tagName}")
        return 0
    except KeyboardInterrupt:
        print("Publish interrupted.", file=sys.stderr)
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
