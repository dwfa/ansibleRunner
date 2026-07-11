#!/usr/bin/env python3
##############################################################################
# Run ansibleRunner tests with self-bootstrapped pytest tooling.
#
# USAGE:
#   ./scripts/test.py
#   ./scripts/test.py unit
#   ./scripts/test.py -b
#   ./scripts/test.py -u -b -w
#   ./scripts/test.py all
#   ./scripts/test.py unit/testRunnerExecution.py
#
# EXIT CODES:
#   - 0: Selected tests completed successfully.
#   - 1: Test target validation failed.
#   - 130: Test run was interrupted by Ctrl-C.
#   - pip/pytest return code: Dependency installation or tests failed.
#
# WORKFLOW:
#   1. Validate that the script is running from an ansibleRunner source tree.
#   2. Bootstrap pytest into a project virtual environment when needed.
#   3. Resolve named scopes or path targets to pytest arguments.
#   4. Run pytest and print its final count summary.
#
# Copyright 2026 Douglas WF Acheson (dwfa@dwfa.ca)
# Licensed under Apache License 2.0. See LICENSE.md for details.
#
# Version: 1.0
# Date: July 06, 2026
##############################################################################

from __future__ import annotations

import argparse
import logging
import os
import re
import subprocess
import sys
import tempfile
import venv
from dataclasses import dataclass
from pathlib import Path


PROJECT_NAME = "ansibleRunner"
TEST_REQUIREMENTS = [
    "pytest>=8",
    "pytest-asyncio>=0.23",
    "textual>=0.89",
]
PYTEST_SUMMARY_PATTERN = re.compile(
    r"=+\s*(?P<summary>\d+\s+(?:passed|failed|errors?|skipped|xfailed|xpassed)"
    r"(?:,\s*\d+\s+(?:passed|failed|errors?|skipped|xfailed|xpassed))*"
    r"\s+in\s+[\d.]+s)\s*=+",
)
TEST_SCOPES = {
    "all": "tests",
    "blackBox": "tests/blackBox",
    "endToEnd": "tests/endToEnd",
    "internals": "tests/internals",
    "unit": "tests/unit",
    "whiteBox": "tests/whiteBox",
}


@dataclass(frozen=True)
class TestRunResult:
    """Result details for a completed pytest run.

    Args:
        returnCode: Pytest process return code.
        summary: Final pytest count summary when detected.
    """

    returnCode: int
    summary: str


def parseArgs(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse command-line arguments for the test helper.

    Args:
        argv: Optional argument list. Uses process arguments when omitted.

    Returns:
        Parsed command-line namespace.
    """

    parser = argparse.ArgumentParser(
        description="Run ansibleRunner tests with self-bootstrapped pytest.",
    )
    parser.add_argument(
        "targets",
        nargs="*",
        default=[],
        help=(
            "Test scopes or paths to run. Known scopes: "
            + ", ".join(sorted(TEST_SCOPES))
            + ". Defaults to unit."
        ),
    )
    parser.add_argument(
        "-b",
        "--black",
        action="store_true",
        help="Run black-box tests.",
    )
    parser.add_argument(
        "--python",
        default=sys.executable,
        help="Python executable used for pytest when it already has pytest.",
    )
    parser.add_argument(
        "-u",
        "--unit",
        action="store_true",
        help="Run unit tests. This is the default when no scope is selected.",
    )
    parser.add_argument(
        "--venv-dir",
        dest="venvDir",
        default=".venv",
        help="Virtual environment directory used for test bootstrapping.",
    )
    parser.add_argument(
        "-w",
        "--white",
        action="store_true",
        help="Run white-box tests.",
    )
    return parser.parse_args(argv)


def selectedTargets(args: argparse.Namespace) -> list[str]:
    """Resolve additive CLI switches into test targets.

    Args:
        args: Parsed command-line namespace.

    Returns:
        Selected scope and path targets.
    """

    targets = list(args.targets)
    if args.unit:
        targets.append("unit")
    if args.black:
        targets.append("blackBox")
    if args.white:
        targets.append("whiteBox")
    return targets or ["unit"]


def runCommand(
    command: list[str],
    cwd: Path | str | None = None,
    logger: logging.Logger | None = None,
) -> subprocess.CompletedProcess[str]:
    """Run a command while optionally logging full stdout and stderr details.

    Args:
        command: Command and arguments to run.
        cwd: Optional working directory for the command.
        logger: Optional logger receiving command details.

    Returns:
        Completed process result.
    """

    if logger is not None:
        logger.info("<test.runCommand> command=[%s]", " ".join(command))
        logger.info("<test.runCommand> cwd=[%s]", cwd or Path.cwd())

    result = subprocess.run(
        command,
        capture_output=True,
        check=False,
        cwd=cwd,
        text=True,
    )

    if logger is not None:
        logger.info("<test.runCommand> returnCode=[%s]", result.returncode)
        if result.stdout:
            logger.debug("<test.runCommand> stdout=[%s]", result.stdout.rstrip())
        if result.stderr:
            logger.debug("<test.runCommand> stderr=[%s]", result.stderr.rstrip())
    return result


def requireProjectRoot(projectRoot: Path) -> None:
    """Validate that the script is running from the expected project root.

    Args:
        projectRoot: Project root containing pyproject.toml.

    Raises:
        SystemExit: When required project files are missing.
    """

    requiredPaths = [
        projectRoot / "pyproject.toml",
        projectRoot / "src" / PROJECT_NAME,
    ]
    missingPaths = [path for path in requiredPaths if not path.exists()]
    if not missingPaths:
        return

    missingText = "\n".join(f"  - {path}" for path in missingPaths)
    raise SystemExit(
        "Cannot run tests because this does not look like the "
        f"{PROJECT_NAME} project root.\nMissing:\n{missingText}"
    )


def hasTestRequirements(pythonBin: str, logger: logging.Logger | None = None) -> bool:
    """Check whether a Python executable has required test packages.

    Args:
        pythonBin: Python executable to inspect.
        logger: Optional logger receiving command details.

    Returns:
        True when required test packages are available, otherwise False.
    """

    checkCommand = [
        pythonBin,
        "-c",
        (
            "import importlib.metadata as m\n"
            "from sys import exit\n"
            "try:\n"
            "    parts = m.version('pytest').split('.')\n"
            "    version = (int(parts[0]), int(parts[1]) if len(parts) > 1 else 0)\n"
            "    pytest_asyncio = m.version('pytest-asyncio').split('.')\n"
            "    pytest_asyncio_version = (int(pytest_asyncio[0]), int(pytest_asyncio[1]) if len(pytest_asyncio) > 1 else 0)\n"
            "    textual = m.version('textual').split('.')\n"
            "    textual_version = (int(textual[0]), int(textual[1]) if len(textual) > 1 else 0)\n"
            "    exit(0 if version >= (8, 0) and pytest_asyncio_version >= (0, 23) and textual_version >= (0, 89) else 1)\n"
            "except Exception:\n"
            "    exit(1)\n"
        ),
    ]
    result = runCommand(checkCommand, cwd=tempfile.gettempdir(), logger=logger)
    return result.returncode == 0


def createVenv(venvDir: Path) -> None:
    """Create a virtual environment when it does not already exist.

    Args:
        venvDir: Virtual environment directory.
    """

    if venvDir.exists():
        return
    print(f"Creating test virtual environment: {venvDir}")
    venv.create(venvDir, with_pip=True)


def getVenvPython(venvDir: Path) -> Path:
    """Return the Python executable path for a virtual environment.

    Args:
        venvDir: Virtual environment directory.

    Returns:
        Path to the virtual environment Python executable.
    """

    if os.name == "nt":
        return venvDir / "Scripts" / "python.exe"
    return venvDir / "bin" / "python"


def installTestRequirements(
    pythonBin: Path,
    logger: logging.Logger | None = None,
) -> None:
    """Install test requirements into the selected Python environment.

    Args:
        pythonBin: Python executable that receives test dependencies.
        logger: Optional logger receiving command details.

    Raises:
        SystemExit: When pip installation fails.
    """

    command = [
        str(pythonBin),
        "-m",
        "pip",
        "install",
        *TEST_REQUIREMENTS,
    ]
    print(f"Installing test requirements: {', '.join(TEST_REQUIREMENTS)}")
    result = runCommand(command, logger=logger)
    if result.stdout:
        print(result.stdout, end="")
    if result.stderr:
        print(result.stderr, end="", file=sys.stderr)
    if result.returncode != 0:
        raise SystemExit(result.returncode)


def ensureTestPython(
    projectRoot: Path,
    pythonBin: str,
    venvDir: str,
    logger: logging.Logger | None = None,
) -> str:
    """Return a Python executable that can run pytest.

    Args:
        projectRoot: Project root containing pyproject.toml.
        pythonBin: Preferred Python executable from the CLI or caller.
        venvDir: Virtual environment path relative to projectRoot unless absolute.
        logger: Optional logger receiving command details.

    Returns:
        Python executable with pytest available.
    """

    if hasTestRequirements(pythonBin, logger=logger):
        return pythonBin

    resolvedVenvDir = Path(venvDir).expanduser()
    if not resolvedVenvDir.is_absolute():
        resolvedVenvDir = projectRoot / resolvedVenvDir
    createVenv(resolvedVenvDir)
    venvPython = getVenvPython(resolvedVenvDir)

    if not hasTestRequirements(str(venvPython), logger=logger):
        installTestRequirements(venvPython, logger=logger)
    return str(venvPython)


def resolveTestTargets(projectRoot: Path, targets: list[str] | None = None) -> list[str]:
    """Resolve test scopes and path targets to pytest arguments.

    Args:
        projectRoot: Project root containing the tests directory.
        targets: Optional scope names or paths. Defaults to unit tests.

    Returns:
        Pytest target arguments relative to projectRoot.

    Raises:
        SystemExit: When a target cannot be resolved.
    """

    requestedTargets = targets or ["unit"]
    resolvedTargets: list[str] = []

    for target in requestedTargets:
        if target in TEST_SCOPES:
            resolvedTargets.append(TEST_SCOPES[target])
            continue

        targetPath = Path(target)
        candidates = [
            projectRoot / targetPath,
            projectRoot / "tests" / targetPath,
        ]
        for candidate in candidates:
            if candidate.exists():
                resolvedTargets.append(str(candidate.relative_to(projectRoot)))
                break
        else:
            knownScopes = ", ".join(sorted(TEST_SCOPES))
            raise SystemExit(
                f"Unknown test target: {target}\n"
                f"Known scopes: {knownScopes}\n"
                "Targets may also be paths relative to the project root or tests/."
            )

    return resolvedTargets


def summarizePytestOutput(output: str) -> str:
    """Extract pytest's final test-count summary.

    Args:
        output: Captured pytest stdout.

    Returns:
        Summary text such as ``23 passed in 0.29s`` when available.
    """

    matches = list(PYTEST_SUMMARY_PATTERN.finditer(output))
    if not matches:
        return ""
    return matches[-1].group("summary")


def runTestSuite(
    projectRoot: Path,
    pythonBin: str,
    targets: list[str] | None = None,
    emitOutput: bool = True,
    logger: logging.Logger | None = None,
) -> TestRunResult:
    """Run pytest for selected targets.

    Args:
        projectRoot: Project root containing pyproject.toml.
        pythonBin: Python executable with pytest available.
        targets: Optional scope names or paths. Defaults to unit tests.
        emitOutput: Whether to print captured pytest output to the terminal.
        logger: Optional logger receiving command details.

    Returns:
        Test result details including return code and summary.
    """

    pytestTargets = resolveTestTargets(projectRoot, targets)
    command = [
        pythonBin,
        "-m",
        "pytest",
        *pytestTargets,
    ]
    result = runCommand(command, cwd=projectRoot, logger=logger)
    if emitOutput and result.stdout:
        print(result.stdout, end="")
    if emitOutput and result.stderr:
        print(result.stderr, end="", file=sys.stderr)
    return TestRunResult(
        returnCode=result.returncode,
        summary=summarizePytestOutput(result.stdout),
    )


def main(argv: list[str] | None = None) -> int:
    """Run the standalone test helper.

    Args:
        argv: Optional argument list. Uses process arguments when omitted.

    Returns:
        Process exit code.
    """

    args = parseArgs(argv)
    projectRoot = Path(__file__).resolve().parent.parent

    try:
        requireProjectRoot(projectRoot)
        testPython = ensureTestPython(projectRoot, args.python, args.venvDir)
        result = runTestSuite(projectRoot, testPython, selectedTargets(args))
        if result.summary:
            print(f"Tests passed: {result.summary}")
        return result.returnCode
    except KeyboardInterrupt:
        print("Test run interrupted.", file=sys.stderr)
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
