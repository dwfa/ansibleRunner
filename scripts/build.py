#!/usr/bin/env python3
##############################################################################
# Test and build the ansibleRunner wheel distribution.
#
# USAGE:
#   ./scripts/build.py
#   python3 scripts/build.py
#
# OUTPUT VARIABLES:
#   - dist/*.whl: Installable Python wheel distribution.
#
# EXIT CODES:
#   - 0: Tests and wheel build completed successfully.
#   - 1: Project validation or wheel discovery failed.
#   - 130: Build was interrupted by Ctrl-C.
#   - pip/pytest/build return code: Dependency installation, tests, or wheel
#     build failed.
#
# WORKFLOW:
#   1. Validate that the script is running from an ansibleRunner source tree.
#   2. Configure full-detail logging.
#   3. Bootstrap test and build tooling into a project virtual environment.
#   4. Run the pytest test suite.
#   5. Build a wheel into the dist directory.
#   6. Prune old build logs.
#   7. Report the generated wheel path.
#
# NOTES:
#   - Test and build dependencies are installed automatically into .venv when
#     missing.
#   - Full command output is written to logs/build-<dts>.log by default.
#
# Copyright 2026 Douglas WF Acheson (dwfa@dwfa.ca)
# Licensed under Apache License 2.0. See LICENSE.md for details.
#
# Version: 1.0
# Date: July 05, 2026
##############################################################################

from __future__ import annotations

import argparse
import importlib.util
import logging
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import textwrap
import time
import unicodedata
import venv
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path


PROJECT_NAME = "ansibleRunner"
TOOL_REQUIREMENTS = [
    "build>=1.2",
    "pytest>=8",
    "pytest-asyncio>=0.23",
    "setuptools>=77",
    "textual>=0.89",
    "wheel",
]
LOG_FILE_ENV_VAR = "ANSIBLE_RUNNER_BUILD_LOG"
GREEN_COLOUR = "\033[38;5;46m"
MAUVE_COLOUR = "\033[38;5;213m"
RESET_COLOUR = "\033[0m"
SUBTLE_WHITE_COLOUR = "\033[38;5;250m"
ANSI_PATTERN_TEXT = "\033\\[[0-9;]*m"
HIDE_CURSOR = "\033[?25l"
SHOW_CURSOR = "\033[?25h"


@dataclass(frozen=True)
class BuildContext:
    """Runtime paths and logger for a build run.

    Args:
        logFile: Path receiving full build diagnostics.
        logger: Configured build logger.
        outDir: Directory receiving wheel artifacts.
        projectRoot: Project root containing pyproject.toml.
        ui: Terminal UI helper.
    """

    logFile: Path
    logger: logging.Logger
    outDir: Path
    projectRoot: Path
    ui: "BuildUi"


@dataclass
class BuildUi:
    """Terminal output helper for macro build steps.

    Args:
        logFile: Path receiving full build diagnostics.
        spinner: Whether to animate active steps.
        verbose: Whether to print substeps to the terminal.
    """

    logFile: Path
    spinner: bool = True
    verbose: bool = False
    activeStep: str | None = None
    activeStepPrinted: bool = False
    activeStepSubstepCount: int = 0
    bodyLineCount: int = 0
    cursorHidden: bool = False
    panelLineCount: int = 0
    spinnerEvent: threading.Event = field(default_factory=threading.Event)
    spinnerThread: threading.Thread | None = None

    def _colour(self, text: str) -> str:
        """Apply neon mauve terminal colour to panel line text.

        Args:
            text: Text to colour.

        Returns:
            Colourized text when stdout is a terminal, otherwise plain text.
        """

        if not sys.stdout.isatty():
            return text
        return f"{MAUVE_COLOUR}{text}{RESET_COLOUR}"

    def _green(self, text: str) -> str:
        """Apply green terminal colour to completion detail text.

        Args:
            text: Text to colour.

        Returns:
            Colourized text when stdout is a terminal, otherwise plain text.
        """

        if not sys.stdout.isatty():
            return text
        return f"{GREEN_COLOUR}{text}{RESET_COLOUR}"

    def _subtleWhite(self, text: str) -> str:
        """Apply subtle white terminal colour to secondary detail text.

        Args:
            text: Text to colour.

        Returns:
            Colourized text when stdout is a terminal, otherwise plain text.
        """

        if not sys.stdout.isatty():
            return text
        return f"{SUBTLE_WHITE_COLOUR}{text}{RESET_COLOUR}"

    def _plainText(self, text: str) -> str:
        """Remove ANSI colour sequences from text.

        Args:
            text: Text that may contain ANSI colour sequences.

        Returns:
            Plain text without ANSI colour sequences.
        """

        import re

        return re.sub(ANSI_PATTERN_TEXT, "", text)

    def _displayWidth(self, text: str) -> int:
        """Calculate terminal display width for text.

        Args:
            text: Text to measure.

        Returns:
            Approximate terminal display column width.
        """

        width = 0
        for character in self._plainText(text):
            codepoint = ord(character)
            if unicodedata.combining(character):
                continue
            if codepoint in {0xFE0E, 0xFE0F}:
                continue
            if (
                0x1F000 <= codepoint <= 0x1FAFF
                or 0x2600 <= codepoint <= 0x27BF
                or unicodedata.east_asian_width(character) in {"F", "W"}
            ):
                width += 2
            else:
                width += 1
        return width

    def _padRight(self, text: str, width: int) -> str:
        """Pad text to a target terminal display width.

        Args:
            text: Text to pad.
            width: Target display width.

        Returns:
            Text padded with trailing spaces.
        """

        return text + (" " * max(0, width - self._displayWidth(text)))

    def _truncateRight(self, text: str, width: int) -> str:
        """Truncate text to a target terminal display width.

        Args:
            text: Text to truncate.
            width: Maximum display width.

        Returns:
            Text truncated with an ellipsis when needed.
        """

        if self._displayWidth(text) <= width:
            return text
        if width <= 1:
            return "…"[:width]

        plainText = self._plainText(text)
        output = ""
        currentWidth = 0
        targetWidth = width - 1
        for character in plainText:
            characterWidth = self._displayWidth(character)
            if currentWidth + characterWidth > targetWidth:
                break
            output += character
            currentWidth += characterWidth
        return output + "…"

    def _panelWidth(self) -> int:
        """Calculate a centered panel width from the current terminal.

        Returns:
            Panel width equal to 95 percent of terminal columns.
        """

        columns = shutil.get_terminal_size(fallback=(100, 24)).columns
        return max(50, min(columns, int(columns * 0.95)))

    def _leftPadding(self, width: int) -> str:
        """Calculate left padding for a centered fixed-width block.

        Args:
            width: Total block width.

        Returns:
            Left padding string.
        """

        columns = shutil.get_terminal_size(fallback=(100, 24)).columns
        leftPadding = max(0, (columns - width) // 2)
        return " " * leftPadding

    def _leftPaddingWidth(self, width: int) -> int:
        """Calculate left padding width for a centered fixed-width block.

        Args:
            width: Total block width.

        Returns:
            Number of left padding columns.
        """

        columns = shutil.get_terminal_size(fallback=(100, 24)).columns
        return max(0, (columns - width) // 2)

    def _panelLine(self, content: str, width: int) -> str:
        """Format a content line for the header panel.

        Args:
            content: Text to place in the panel.
            width: Total panel width.

        Returns:
            Formatted panel line.
        """

        innerWidth = width - 4
        paddedContent = self._padRight(content, innerWidth)
        left = self._colour("│")
        right = self._colour("│")
        return f"{self._leftPadding(width)}{left} {paddedContent} {right}"

    def _clearLine(self) -> None:
        """Clear the current terminal line."""

        if sys.stdout.isatty():
            print("\r\033[K", end="", flush=True)

    def hideCursor(self) -> None:
        """Hide the terminal cursor while animated status output is active."""

        if sys.stdout.isatty() and not self.cursorHidden:
            print(HIDE_CURSOR, end="", flush=True)
            self.cursorHidden = True

    def showCursor(self) -> None:
        """Restore the terminal cursor after animated status output finishes."""

        if sys.stdout.isatty() and self.cursorHidden:
            print(SHOW_CURSOR, end="", flush=True)
            self.cursorHidden = False

    def _stepLine(self, title: str, prefix: str, suffix: str = "") -> str:
        """Format a build step line inside the panel-width block.

        Args:
            title: Step title.
            prefix: Left-side status marker or spinner.
            suffix: Optional right-side completion marker.

        Returns:
            Formatted step line.
        """

        width = self._panelWidth()
        leftText = f"{prefix} {title}" if prefix else f" {title}"
        suffixWidth = self._displayWidth(suffix)
        availableWidth = max(1, width - suffixWidth)
        fittedLeft = self._truncateRight(leftText, availableWidth)
        paddedLeft = self._padRight(fittedLeft, availableWidth)
        return f"{self._leftPadding(width)}{paddedLeft}{suffix}"

    def _printTtyStatusLine(self, title: str, prefix: str, suffix: str = "") -> None:
        """Print a status line with suffix placed at a fixed terminal column.

        Args:
            title: Status title.
            prefix: Left-side status marker or spinner.
            suffix: Optional right-side completion marker.
        """

        width = self._panelWidth()
        leftPadding = self._leftPaddingWidth(width)
        leftText = f"{prefix} {title}" if prefix else f" {title}"
        suffixWidth = self._displayWidth(suffix)
        availableWidth = max(1, width - suffixWidth)
        fittedLeft = self._truncateRight(leftText, availableWidth)
        suffixColumn = leftPadding + width - suffixWidth + 1
        print(f"\r\033[K{' ' * leftPadding}{fittedLeft}", end="", flush=True)
        if suffix:
            print(f"\033[{suffixColumn}G{suffix}", end="", flush=True)

    def _renderSpinner(self) -> None:
        """Render the active step spinner until it is stopped."""

        frames = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]
        frameIndex = 0
        while not self.spinnerEvent.is_set():
            if self.activeStep is not None:
                self._printTtyStatusLine(self.activeStep, "", frames[frameIndex])
            frameIndex = (frameIndex + 1) % len(frames)
            time.sleep(0.1)

    def _stopSpinner(self) -> None:
        """Stop and join the active spinner thread."""

        self.spinnerEvent.set()
        if self.spinnerThread is not None:
            self.spinnerThread.join(timeout=1)
            self.spinnerThread = None

    def _headerLines(self, wheelName: str | None = None) -> list[str]:
        """Build the centered header panel lines.

        Args:
            wheelName: Optional completed wheel filename.

        Returns:
            Header panel lines.
        """

        width = self._panelWidth()
        innerWidth = width - 4
        top = self._colour("╭" + ("─" * (width - 2)) + "╮")
        bottom = self._colour("╰" + ("─" * (width - 2)) + "╯")
        wheelLabel = self._green(wheelName) if wheelName else "TBD"
        title = f"🚀 {PROJECT_NAME} Test + Wheel Build ({wheelLabel})"
        logText = f"Log: {self.logFile}"
        logLines = textwrap.wrap(logText, width=innerWidth) or [logText]

        lines = [
            f"{self._leftPadding(width)}{top}",
            self._panelLine(self._truncateRight(title, innerWidth), width),
            self._panelLine("", width),
        ]
        lines.extend(self._panelLine(line, width) for line in logLines)
        lines.append(f"{self._leftPadding(width)}{bottom}")
        return lines

    def header(self) -> None:
        """Print the centered build header panel."""

        lines = self._headerLines()
        self.panelLineCount = len(lines)
        self.bodyLineCount = 0
        print("\n".join(lines), flush=True)

    def completeHeader(self, wheelPath: Path) -> None:
        """Update the header title after a successful wheel build.

        Args:
            wheelPath: Generated wheel path.
        """

        if not sys.stdout.isatty() or self.panelLineCount == 0:
            return

        moveUp = self.panelLineCount + self.bodyLineCount
        print(f"\033[{moveUp}F", end="", flush=True)
        lines = self._headerLines(wheelPath.name)
        print("\n".join(f"\r\033[K{line}" for line in lines), flush=True)
        if self.bodyLineCount:
            print(f"\033[{self.bodyLineCount}E", end="", flush=True)

    def step(self, title: str) -> None:
        """Start a macro step spinner.

        Args:
            title: Step title.
        """

        self.finishStep()
        self.activeStep = title
        self.activeStepPrinted = False
        self.activeStepSubstepCount = 0
        self.spinnerEvent = threading.Event()
        if self.verbose and not sys.stdout.isatty():
            print(self._stepLine(title, "•"), flush=True)
            self.bodyLineCount += 1
            self.activeStepPrinted = True
        elif self.spinner and sys.stdout.isatty():
            self.spinnerThread = threading.Thread(
                target=self._renderSpinner,
                daemon=True,
            )
            self.spinnerThread.start()
        elif sys.stdout.isatty():
            self._printTtyStatusLine(title, "•")
        else:
            print(self._stepLine(title, "•"), flush=True)
            self.bodyLineCount += 1

    def finishStep(self, success: bool = True) -> None:
        """Stop the active step spinner and write its final status.

        Args:
            success: Whether the active step completed successfully.
        """

        if self.activeStep is None:
            return

        title = self.activeStep
        self._stopSpinner()

        if self.verbose and self.activeStepPrinted and sys.stdout.isatty():
            suffix = "✅" if success else "❌"
            moveUp = self.activeStepSubstepCount + 1
            print(f"\033[{moveUp}F", end="", flush=True)
            self._printTtyStatusLine(title, "", suffix)
            print(flush=True)
            if self.activeStepSubstepCount:
                print(f"\033[{self.activeStepSubstepCount}E", end="", flush=True)
        elif self.verbose and self.activeStepPrinted:
            suffix = "✅" if success else "❌"
            print(self._stepLine(title, "", suffix), flush=True)
            self.bodyLineCount += 1
        elif sys.stdout.isatty():
            suffix = "✅" if success else "❌"
            self._printTtyStatusLine(title, "", suffix)
            print(flush=True)
            self.bodyLineCount += 1

        self.activeStep = None
        self.activeStepPrinted = False
        self.activeStepSubstepCount = 0

    def cancelStep(self) -> None:
        """Stop the active step without adding a new completed step line."""

        if self.activeStep is None:
            return

        title = self.activeStep
        self._stopSpinner()

        if self.verbose and self.activeStepPrinted and sys.stdout.isatty():
            moveUp = self.activeStepSubstepCount + 1
            print(f"\033[{moveUp}F", end="", flush=True)
            self._printTtyStatusLine(title, "", "❌")
            print(flush=True)
            if self.activeStepSubstepCount:
                print(f"\033[{self.activeStepSubstepCount}E", end="", flush=True)
        elif self.verbose and self.activeStepPrinted:
            print(self._stepLine(title, "", "❌"), flush=True)
            self.bodyLineCount += 1
        elif sys.stdout.isatty():
            self._clearLine()

        self.activeStep = None
        self.activeStepPrinted = False
        self.activeStepSubstepCount = 0

    def materializeActiveStep(self) -> None:
        """Convert a live spinner step into a persistent parent line."""

        if self.activeStep is None or self.activeStepPrinted:
            return

        title = self.activeStep
        self._stopSpinner()

        if sys.stdout.isatty():
            self._clearLine()

        print(self._stepLine(title, "•"), flush=True)
        self.bodyLineCount += 1
        self.activeStepPrinted = True

    def substep(self, detail: str) -> None:
        """Print a verbose substep when verbose mode is enabled.

        Args:
            detail: Substep detail.
        """

        if self.verbose:
            self.materializeActiveStep()
            substepLine = f"{self._leftPadding(self._panelWidth())}      ╰─ {detail}"
            print(
                self._subtleWhite(substepLine),
                flush=True,
            )
            self.bodyLineCount += 1
            if self.activeStep is not None:
                self.activeStepSubstepCount += 1

    def summarySubstep(self, detail: str) -> None:
        """Print an important substep in verbose or captured output.

        Args:
            detail: Substep detail.
        """

        if self.verbose:
            self.substep(detail)
            return
        if sys.stdout.isatty():
            return

        substepLine = f"{self._leftPadding(self._panelWidth())}      ╰─ {detail}"
        print(self._subtleWhite(substepLine), flush=True)
        self.bodyLineCount += 1

    def success(self, message: str) -> None:
        """Print a success message.

        Args:
            message: Message to display.
        """

        self.finishStep()
        completedMessage = f"🎉 {message}"
        if sys.stdout.isatty():
            self._printTtyStatusLine(completedMessage, "", "✅")
            print(flush=True)
            self.bodyLineCount += 1
            return

        print(self._stepLine(completedMessage, "", "✅"), flush=True)
        self.bodyLineCount += 1

    def failure(self, message: str) -> None:
        """Print a failure message.

        Args:
            message: Message to display.
        """

        self.finishStep(False)
        if sys.stdout.isatty():
            self._printTtyStatusLine(message, "", "❌")
            print(flush=True)
            self.bodyLineCount += 1
            return

        print(self._stepLine(message, "", "❌"), flush=True)
        self.bodyLineCount += 1


def parseArgs(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse command-line arguments for the wheel build helper.

    Args:
        argv: Optional argument list. Uses process arguments when omitted.

    Returns:
        Parsed command-line namespace.
    """

    parser = argparse.ArgumentParser(
        description="Test and build the ansibleRunner wheel distribution.",
    )
    parser.add_argument(
        "--out-dir",
        dest="outDir",
        default="dist",
        help="Directory where the wheel will be written. Defaults to dist.",
    )
    parser.add_argument(
        "--python",
        default=sys.executable,
        help="Python executable used to run the build module.",
    )
    parser.add_argument(
        "--venv-dir",
        dest="venvDir",
        default=".venv",
        help="Virtual environment directory used for build bootstrapping.",
    )
    parser.add_argument(
        "--log-file",
        dest="logFile",
        default=None,
        help="Full-detail build log file. Defaults to logs/build-<dts>.log.",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Show build substeps on screen.",
    )
    parser.add_argument(
        "--no-spinner",
        dest="noSpinner",
        action="store_true",
        help="Disable animated step spinner.",
    )
    return parser.parse_args(argv)


def configureLogging(projectRoot: Path, logFileArg: str | None) -> tuple[Path, logging.Logger]:
    """Configure full-detail build logging.

    Args:
        projectRoot: Project root containing pyproject.toml.
        logFileArg: Optional log file path from the CLI.

    Returns:
        Tuple containing the log file path and configured logger.
    """

    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    defaultLogFile = projectRoot / "logs" / f"build-{timestamp}.log"
    logFile = Path(
        os.environ.get(LOG_FILE_ENV_VAR) or logFileArg or defaultLogFile
    ).expanduser()
    if not logFile.is_absolute():
        logFile = projectRoot / logFile
    logFile.parent.mkdir(parents=True, exist_ok=True)

    logger = logging.getLogger("ansibleRunner.build")
    logger.setLevel(logging.DEBUG)
    logger.handlers.clear()
    logger.propagate = False

    handler = logging.FileHandler(logFile, encoding="utf-8")
    handler.setFormatter(
        logging.Formatter("%(asctime)s %(levelname)s %(message)s")
    )
    logger.addHandler(handler)
    logger.info("<configureLogging> logFile=[%s]", logFile)
    return logFile, logger


def runCommand(
    command: list[str],
    logger: logging.Logger,
    cwd: Path | str | None = None,
) -> subprocess.CompletedProcess[str]:
    """Run a command while logging full stdout and stderr details.

    Args:
        command: Command and arguments to run.
        logger: Logger receiving command details.
        cwd: Optional working directory for the command.

    Returns:
        Completed process result.
    """

    logger.info("<runCommand> command=[%s]", " ".join(command))
    logger.info("<runCommand> cwd=[%s]", cwd or Path.cwd())
    result = subprocess.run(
        command,
        capture_output=True,
        check=False,
        cwd=cwd,
        text=True,
    )
    logger.info("<runCommand> returnCode=[%s]", result.returncode)
    if result.stdout:
        logger.debug("<runCommand> stdout=[%s]", result.stdout.rstrip())
    if result.stderr:
        logger.debug("<runCommand> stderr=[%s]", result.stderr.rstrip())
    return result


def startStep(context: BuildContext, title: str) -> None:
    """Start a macro build step on screen and in the log.

    Args:
        context: Build runtime context.
        title: Step title.
    """

    sectionLine = "=" * 78
    context.logger.info("")
    context.logger.info(sectionLine)
    context.logger.info("<startStep> %s", title)
    context.logger.info(sectionLine)
    context.ui.step(title)


def hasToolRequirements(pythonBin: str, logger: logging.Logger) -> bool:
    """Check whether a Python executable has required tool packages.

    Args:
        pythonBin: Python executable to inspect.
        logger: Logger receiving command details.

    Returns:
        True when required build packages are available, otherwise False.
    """

    checkCommand = [
        pythonBin,
        "-c",
        (
            "import importlib.metadata as m\n"
            "from sys import exit\n"
            "def ok(name, major=0, minor=0):\n"
            "    try:\n"
            "        parts = m.version(name).split('.')\n"
            "        version = (int(parts[0]), int(parts[1]) if len(parts) > 1 else 0)\n"
            "        return version >= (major, minor)\n"
            "    except Exception:\n"
            "        return False\n"
            "exit(0 if ok('build', 1, 2) and ok('setuptools', 77, 0) "
        "and ok('pytest', 8, 0) and ok('pytest-asyncio', 0, 23) "
        "and ok('textual', 0, 89) and ok('wheel') else 1)\n"
        ),
    ]
    result = runCommand(
        checkCommand,
        logger,
        cwd=tempfile.gettempdir(),
    )
    return result.returncode == 0


def createVenv(venvDir: Path, context: BuildContext) -> None:
    """Create a virtual environment when it does not already exist.

    Args:
        venvDir: Virtual environment directory.
        context: Build runtime context.
    """

    if venvDir.exists():
        context.logger.info("<createVenv> existingVenv=[%s]", venvDir)
        context.ui.substep(f"Using existing virtual environment: {venvDir}")
        return

    context.logger.info("<createVenv> creatingVenv=[%s]", venvDir)
    context.ui.substep(f"Creating virtual environment: {venvDir}")
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


def installToolRequirements(pythonBin: Path, context: BuildContext) -> None:
    """Install test and build requirements into the selected Python environment.

    Args:
        pythonBin: Python executable that receives build dependencies.
        context: Build runtime context.

    Raises:
        SystemExit: When pip installation fails.
    """

    command = [
        str(pythonBin),
        "-m",
        "pip",
        "install",
        *TOOL_REQUIREMENTS,
    ]
    context.ui.substep(f"Installing tool requirements: {', '.join(TOOL_REQUIREMENTS)}")
    result = runCommand(command, context.logger)

    if result.returncode != 0:
        context.ui.failure("Dependency install failed. See log for more details.")
        raise SystemExit(result.returncode)


def ensureBuildPython(context: BuildContext, args: argparse.Namespace) -> str:
    """Return a Python executable that can run the build module.

    Args:
        context: Build runtime context.
        args: Parsed command-line arguments.

    Returns:
        Python executable with the build module available.
    """

    context.logger.debug("<ensureBuildPython> entry: python=[%s]", args.python)
    startStep(context, "🧰 Prepare build environment")
    context.ui.substep(f"Checking Python: {args.python}")
    if hasToolRequirements(args.python, context.logger):
        context.logger.debug("<ensureBuildPython> exit: usingPython=[%s]", args.python)
        context.ui.substep("Selected Python already has test/build requirements.")
        return args.python

    venvDir = (context.projectRoot / args.venvDir).resolve()
    createVenv(venvDir, context)
    venvPython = getVenvPython(venvDir)
    context.ui.substep(f"Checking virtual environment Python: {venvPython}")

    if not hasToolRequirements(str(venvPython), context.logger):
        installToolRequirements(venvPython, context)

    context.logger.debug(
        "<ensureBuildPython> exit: bootstrappedPython=[%s]",
        venvPython,
    )
    context.ui.substep(f"Using build Python: {venvPython}")
    return str(venvPython)


def requireProjectRoot(context: BuildContext) -> None:
    """Validate that the script is running from the expected project root.

    Args:
        context: Build runtime context.

    Raises:
        SystemExit: When required project files are missing.
    """

    startStep(context, "🔎 Validate project root")
    requiredPaths = [
        context.projectRoot / "pyproject.toml",
        context.projectRoot / "src" / PROJECT_NAME,
    ]
    missingPaths = [path for path in requiredPaths if not path.exists()]

    if not missingPaths:
        for path in requiredPaths:
            context.ui.substep(f"Found required path: {path}")
        return

    missingText = "\n".join(f"  - {path}" for path in missingPaths)
    context.logger.error("<requireProjectRoot> missingPaths=[%s]", missingText)
    context.ui.failure("Project validation failed. See log for more details.")
    raise SystemExit(
        "Cannot build wheel because this does not look like the "
        f"{PROJECT_NAME} project root.\nMissing:\n{missingText}"
    )


def findWheels(outDir: Path) -> set[Path]:
    """Find wheel files in an output directory.

    Args:
        outDir: Directory to scan.

    Returns:
        Set of wheel paths present in the directory.
    """

    if not outDir.exists():
        return set()
    return set(outDir.glob("*.whl"))


def pruneBuildLogs(context: BuildContext, keepCount: int = 5) -> None:
    """Keep only the newest build logs.

    Args:
        context: Build runtime context.
        keepCount: Number of newest logs to retain.
    """

    startStep(context, "🧹 Clean up old logs")
    logDir = context.logFile.parent
    logs = sorted(
        logDir.glob("build-*.log"),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )
    removableLogs = [
        path for path in logs[keepCount:] if path.resolve() != context.logFile.resolve()
    ]

    context.ui.substep(f"Log directory: {logDir}")
    context.ui.substep(f"Keeping newest {keepCount} build logs.")
    context.logger.info("<pruneBuildLogs> foundLogs=[%s]", len(logs))
    context.logger.info("<pruneBuildLogs> removableLogs=[%s]", len(removableLogs))

    for logPath in removableLogs:
        context.logger.info("<pruneBuildLogs> removingLog=[%s]", logPath)
        logPath.unlink()


def buildWheel(context: BuildContext, pythonBin: str) -> Path:
    """Build the wheel distribution and return the generated wheel path.

    Args:
        context: Build runtime context.
        pythonBin: Python executable used to run the build module.

    Returns:
        Path to the generated wheel.

    Raises:
        SystemExit: When the build fails or no wheel can be identified.
    """

    context.logger.debug("<buildWheel> entry: python=[%s]", pythonBin)
    startStep(context, "🏗️  Build wheel")
    context.ui.substep(f"Output directory: {context.outDir}")
    context.ui.substep(f"Build Python: {pythonBin}")
    context.outDir.mkdir(parents=True, exist_ok=True)
    existingWheels = findWheels(context.outDir)

    command = [
        pythonBin,
        "-m",
        "build",
        str(context.projectRoot),
        "--wheel",
        "--no-isolation",
        "--outdir",
        str(context.outDir),
    ]

    context.ui.substep("Running Python build backend.")
    result = runCommand(
        command,
        context.logger,
        cwd=tempfile.gettempdir(),
    )

    if result.returncode != 0:
        context.ui.failure("Wheel build failed. See log for more details.")
        raise SystemExit(result.returncode)

    newWheels = findWheels(context.outDir) - existingWheels
    if len(newWheels) == 1:
        wheelPath = newWheels.pop()
        context.logger.debug("<buildWheel> exit: wheelPath=[%s]", wheelPath)
        context.ui.substep(f"Generated wheel: {wheelPath}")
        return wheelPath

    allWheels = sorted(
        findWheels(context.outDir),
        key=lambda path: path.stat().st_mtime,
    )
    if allWheels:
        wheelPath = allWheels[-1]
        context.logger.debug("<buildWheel> exit: wheelPath=[%s]", wheelPath)
        context.ui.substep(f"Using newest wheel: {wheelPath}")
        return wheelPath

    context.ui.failure(f"Build finished, but no wheel was found in {context.outDir}.")
    raise SystemExit(f"Build finished, but no wheel was found in {context.outDir}.")


def runTests(context: BuildContext, pythonBin: str) -> None:
    """Run the pytest test suite as a build macro step.

    Args:
        context: Build runtime context.
        pythonBin: Python executable with pytest available.

    Raises:
        SystemExit: When pytest fails.
    """

    context.logger.debug("<runTests> entry: python=[%s]", pythonBin)
    startStep(context, "🧪 Run tests")
    context.ui.substep(f"Test Python: {pythonBin}")
    context.ui.substep("Running unit tests.")
    testScript = loadTestScript(context.projectRoot)
    result = testScript.runTestSuite(
        context.projectRoot,
        pythonBin,
        ["unit"],
        emitOutput=False,
        logger=context.logger,
    )

    if result.returnCode != 0:
        context.ui.failure("Tests failed. See log for more details.")
        raise SystemExit(result.returnCode)

    if result.summary:
        context.ui.activeStep = f"🧪 Run tests ({result.summary})"
        context.ui.summarySubstep(f"Tests passed: {result.summary}")
    context.logger.debug("<runTests> exit: returnCode=[%s]", result.returnCode)


def summarizePytestOutput(output: str) -> str:
    """Extract pytest's final test-count summary.

    Args:
        output: Captured pytest stdout.

    Returns:
        Summary text such as ``23 passed in 0.29s`` when available.
    """

    testScript = loadTestScript(Path(__file__).resolve().parent.parent)
    return testScript.summarizePytestOutput(output)


def loadTestScript(projectRoot: Path) -> object:
    """Load scripts/test.py as an importable helper module.

    Args:
        projectRoot: Project root containing the scripts directory.

    Returns:
        Imported test helper module.
    """

    scriptPath = projectRoot / "scripts" / "test.py"
    spec = importlib.util.spec_from_file_location("ansibleRunnerTestScript", scriptPath)
    assert spec is not None
    assert spec.loader is not None

    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def main(argv: list[str] | None = None) -> int:
    """Run the wheel build helper.

    Args:
        argv: Optional argument list. Uses process arguments when omitted.

    Returns:
        Process exit code.
    """

    args = parseArgs(argv)
    projectRoot = Path(__file__).resolve().parent.parent
    outDir = (projectRoot / args.outDir).resolve()

    logFile, logger = configureLogging(projectRoot, args.logFile)
    ui = BuildUi(
        logFile=logFile,
        spinner=not args.noSpinner,
        verbose=args.verbose,
    )
    context = BuildContext(
        logFile=logFile,
        logger=logger,
        outDir=outDir,
        projectRoot=projectRoot,
        ui=ui,
    )

    logger.debug("<main> entry: argv=[%s]", argv)
    ui.header()
    ui.hideCursor()

    try:
        requireProjectRoot(context)
        buildPython = ensureBuildPython(context, args)
        runTests(context, buildPython)
        wheelPath = buildWheel(context, buildPython)
        pruneBuildLogs(context)

        ui.finishStep()
        ui.completeHeader(wheelPath)
        ui.success("Wheel build complete")
        logger.debug("<main> exit: wheelPath=[%s]", wheelPath)
        return 0
    except KeyboardInterrupt:
        logger.warning("<main> interruptedByUser=[True]")
        ui.cancelStep()
        ui.failure("Build interrupted. See log for more details.")
        return 130
    finally:
        if ui.activeStep is not None:
            ui.finishStep(False)
        ui.showCursor()


if __name__ == "__main__":
    raise SystemExit(main())
