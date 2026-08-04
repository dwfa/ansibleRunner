#!/usr/bin/env python3
##############################################################################
# GitHub bootstrap installer for ansibleRunner.
#
# USAGE:
#   curl -LO https://github.com/dwfa/ansibleRunner/releases/download/v1.0.1/install.py
#   python3 install.py
#
# WORKFLOW:
#   1. Treat the current working directory as the Ansible project root.
#   2. Create .venv under the project root when needed.
#   3. Install ansibleRunner from GitHub into the project .venv.
#   4. Write a thin project-local launcher.
#
# Copyright 2026 Douglas WF Acheson (dwfa@dwfa.ca)
# Licensed under Apache License 2.0. See LICENSE.md for details.
#
# Version: 1.0
# Date: August 03, 2026
##############################################################################

"""Install ansibleRunner from GitHub into a project-local virtual environment."""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import textwrap
import threading
import time
import unicodedata
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path


PACKAGE_NAME = "ansibleRunner"
DEFAULT_VERSION = "1.0.1"
DEFAULT_REPO_URL = "https://github.com/dwfa/ansibleRunner.git"
DEFAULT_REF = f"v{DEFAULT_VERSION}"
DEFAULT_WHEEL_URL = (
    "https://github.com/dwfa/ansibleRunner/releases/download/"
    f"{DEFAULT_REF}/ansiblerunner-{DEFAULT_VERSION}-py3-none-any.whl"
)
DEFAULT_WHEEL_NAME = f"ansiblerunner-{DEFAULT_VERSION}-py3-none-any.whl"
DEFAULT_LAUNCHER_NAME = "ar.py"
GREEN_COLOUR = "\033[38;5;46m"
MAUVE_COLOUR = "\033[38;5;213m"
RESET_COLOUR = "\033[0m"
SUBTLE_WHITE_COLOUR = "\033[38;5;250m"
HIDE_CURSOR = "\033[?25l"
SHOW_CURSOR = "\033[?25h"


@dataclass
class InstallerUi:
    """Terminal output helper for project installation.

    Args:
        logPath: Path receiving full install diagnostics.
    """

    logPath: Path
    activeStep: str | None = None
    activeStepHadSubsteps: bool = False
    activeStepPrinted: bool = False
    cursorHidden: bool = False
    spinnerEvent: threading.Event = field(default_factory=threading.Event)
    spinnerThread: threading.Thread | None = None

    def header(self, projectRoot: Path, venvDir: Path) -> None:
        """Print the installer header panel.

        Args:
            projectRoot: Ansible project root.
            venvDir: Project virtual environment directory.
        """

        width = self._panelWidth()
        innerWidth = width - 4
        top = self._colour("╭" + ("─" * (width - 2)) + "╮")
        bottom = self._colour("╰" + ("─" * (width - 2)) + "╯")
        lines = [
            f"{self._leftPadding(width)}{top}",
            self._panelLine(
                self._truncateRight(f"🚀 {PACKAGE_NAME} Installer ({DEFAULT_REF})", innerWidth),
                width,
            ),
            self._panelLine("", width),
        ]
        for label, value in (
            ("Project", projectRoot),
            ("Venv", venvDir),
            ("Log", self.logPath),
        ):
            detail = f"{label}: {value}"
            wrappedLines = textwrap.wrap(detail, width=innerWidth) or [detail]
            lines.extend(self._panelLine(line, width) for line in wrappedLines)
        lines.append(f"{self._leftPadding(width)}{bottom}")
        print("\n".join(lines), flush=True)

    def step(self, title: str) -> None:
        """Start an installer step.

        Args:
            title: Step title.
        """

        self.activeStep = title
        self.activeStepHadSubsteps = False
        self.activeStepPrinted = False
        if sys.stdout.isatty():
            self.hideCursor()
            self.spinnerEvent = threading.Event()
            self.spinnerThread = threading.Thread(
                target=self._renderSpinner,
                daemon=True,
            )
            self.spinnerThread.start()
        else:
            print(self._stepLine(title, "•"), flush=True)
            self.activeStepPrinted = True

    def finishStep(self, success: bool = True) -> None:
        """Print completion status for the active step.

        Args:
            success: Whether the step completed successfully.
        """

        if self.activeStep is None:
            return
        title = self.activeStep
        self._stopSpinner()
        marker = self._green("✅") if success else "❌"
        if sys.stdout.isatty():
            self._printTtyStatusLine(title, "", marker)
            print(flush=True)
        elif not self.activeStepPrinted:
            print(self._stepLine(title, "•", marker), flush=True)
        self.activeStep = None
        self.activeStepHadSubsteps = False
        self.activeStepPrinted = False

    def substep(self, message: str) -> None:
        """Print an indented detail line.

        Args:
            message: Detail text.
        """

        width = self._panelWidth()
        detail = self._subtleWhite(f"    ╰─ {message}")
        print(f"{self._leftPadding(width)}{detail}", flush=True)
        self.activeStepHadSubsteps = True

    def success(self, launcherPath: Path) -> None:
        """Print final installer success details.

        Args:
            launcherPath: Generated project launcher path.
        """

        print(self._stepLine("🎉 Install complete", " ", self._green("✅")), flush=True)
        self.substep(f"Launcher: {launcherPath}")
        self.substep(f"Run: {launcherPath}")

    def failure(self, message: str) -> None:
        """Print installer failure details.

        Args:
            message: Failure message.
        """

        print(self._stepLine(message, " ", "❌"), flush=True)
        self.substep(f"See log: {self.logPath}")

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

    def cleanup(self) -> None:
        """Stop active animation and restore terminal state."""

        self._stopSpinner()
        self.showCursor()

    def _colour(self, text: str) -> str:
        """Apply panel colour when stdout is a terminal."""

        if not sys.stdout.isatty():
            return text
        return f"{MAUVE_COLOUR}{text}{RESET_COLOUR}"

    def _green(self, text: str) -> str:
        """Apply success colour when stdout is a terminal."""

        if not sys.stdout.isatty():
            return text
        return f"{GREEN_COLOUR}{text}{RESET_COLOUR}"

    def _subtleWhite(self, text: str) -> str:
        """Apply secondary text colour when stdout is a terminal."""

        if not sys.stdout.isatty():
            return text
        return f"{SUBTLE_WHITE_COLOUR}{text}{RESET_COLOUR}"

    def _displayWidth(self, text: str) -> int:
        """Calculate approximate terminal display width."""

        width = 0
        for character in text:
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
        """Pad text to a target display width."""

        return text + (" " * max(0, width - self._displayWidth(text)))

    def _truncateRight(self, text: str, width: int) -> str:
        """Truncate text to a target display width."""

        if self._displayWidth(text) <= width:
            return text
        if width <= 1:
            return "…"[:width]

        output = ""
        currentWidth = 0
        targetWidth = width - 1
        for character in text:
            characterWidth = self._displayWidth(character)
            if currentWidth + characterWidth > targetWidth:
                break
            output += character
            currentWidth += characterWidth
        return output + "…"

    def _panelWidth(self) -> int:
        """Calculate a centered panel width from the current terminal."""

        columns = shutil.get_terminal_size(fallback=(100, 24)).columns
        return max(50, min(columns, int(columns * 0.95)))

    def _leftPadding(self, width: int) -> str:
        """Calculate left padding for a centered block."""

        columns = shutil.get_terminal_size(fallback=(100, 24)).columns
        return " " * max(0, (columns - width) // 2)

    def _panelLine(self, content: str, width: int) -> str:
        """Format one header panel line."""

        innerWidth = width - 4
        left = self._colour("│")
        right = self._colour("│")
        return f"{self._leftPadding(width)}{left} {self._padRight(content, innerWidth)} {right}"

    def _printTtyStatusLine(self, title: str, prefix: str, suffix: str = "") -> None:
        """Print one status line with a fixed right-side suffix column."""

        width = self._panelWidth()
        leftPadding = len(self._leftPadding(width))
        leftText = f"{prefix} {title}" if prefix else f" {title}"
        suffixWidth = self._displayWidth(suffix)
        availableWidth = max(1, width - suffixWidth)
        fittedLeft = self._truncateRight(leftText, availableWidth)
        suffixColumn = leftPadding + width - suffixWidth + 1
        print(f"\r\033[K{' ' * leftPadding}{fittedLeft}", end="", flush=True)
        if suffix:
            print(f"\033[{suffixColumn}G{suffix}", end="", flush=True)

    def _renderSpinner(self) -> None:
        """Render an active step spinner until the step completes."""

        frames = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]
        frameIndex = 0
        while not self.spinnerEvent.is_set():
            if self.activeStep is not None:
                self._printTtyStatusLine(
                    self.activeStep,
                    "",
                    frames[frameIndex],
                )
            frameIndex = (frameIndex + 1) % len(frames)
            time.sleep(0.1)

    def _stopSpinner(self) -> None:
        """Stop and join the active spinner thread."""

        self.spinnerEvent.set()
        if self.spinnerThread is not None:
            self.spinnerThread.join(timeout=1)
            self.spinnerThread = None

    def _stepLine(self, title: str, prefix: str, suffix: str = "") -> str:
        """Format an installer step line."""

        width = self._panelWidth()
        leftText = f"{prefix} {title}" if prefix else f" {title}"
        suffixWidth = self._displayWidth(suffix)
        availableWidth = max(1, width - suffixWidth)
        fittedLeft = self._truncateRight(leftText, availableWidth)
        return f"{self._leftPadding(width)}{self._padRight(fittedLeft, availableWidth)}{suffix}"


def main(argv: list[str] | None = None) -> int:
    """Install ansibleRunner and write a project-local launcher.

    Args:
        argv: Optional arguments excluding the executable name.

    Returns:
        Process exit code.
    """

    args = parseArgs(argv)
    projectRoot = args.projectRoot.expanduser().resolve()
    venvDir = args.venvDir.expanduser()
    if not venvDir.is_absolute():
        venvDir = projectRoot / venvDir
    packageSpec = getPackageSpec(args, projectRoot)
    launcherPath = projectRoot / args.launcherName
    logPath = getInstallLogPath(projectRoot)
    venvPython = getVenvPython(venvDir)
    ui = InstallerUi(logPath)

    ui.header(projectRoot, venvDir)
    try:
        ui.step("🧰 Prepare virtual environment")
        venvCreated = ensureVenv(venvDir, args.python, logPath, args.verbose)
        ui.finishStep()
        if venvCreated:
            ui.substep(f"Created {venvDir} ✅")
        else:
            ui.substep(f"Using existing {venvDir} ✅")

        ui.step("📦 Install ansibleRunner")
        installPackage(venvPython, packageSpec, logPath, args.verbose)
        ui.finishStep()
        ui.substep(f"Installed {PACKAGE_NAME} ✅")

        ui.step("📝 Write project launcher")
        writeLauncher(launcherPath, venvDir)
        ui.finishStep()
        ui.substep(f"Wrote {launcherPath} ✅")
        staleLauncherPath = projectRoot / "ansibleRunner.py"
        if launcherPath.name != "ansibleRunner.py" and staleLauncherPath.exists():
            ui.substep(f"Remove old launcher to avoid recursion: {staleLauncherPath}")
    except SystemExit:
        ui.finishStep(False)
        ui.failure("Install failed")
        raise
    except Exception as exc:
        ui.finishStep(False)
        ui.failure(f"Install failed: {exc}")
        raise
    finally:
        ui.cleanup()

    ui.success(launcherPath)
    return 0


def parseArgs(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse installer arguments.

    Args:
        argv: Optional arguments excluding the executable name.

    Returns:
        Parsed arguments.
    """

    parser = argparse.ArgumentParser(
        description="Install ansibleRunner from GitHub into a project .venv."
    )
    parser.add_argument(
        "--project-root",
        dest="projectRoot",
        type=Path,
        default=Path(os.environ.get("ANSIBLE_RUNNER_PROJECT_ROOT", Path.cwd())),
        help="Ansible project root. Defaults to the current directory.",
    )
    parser.add_argument(
        "--venv-dir",
        dest="venvDir",
        type=Path,
        default=Path(os.environ.get("ANSIBLE_RUNNER_VENV", ".venv")),
        help="Virtual environment path. Relative paths are under project root.",
    )
    parser.add_argument(
        "--python",
        default=os.environ.get("PYTHON", sys.executable),
        help="Python executable used to create the virtual environment.",
    )
    parser.add_argument(
        "--repo-url",
        dest="repoUrl",
        default=os.environ.get("ANSIBLE_RUNNER_REPO_URL", DEFAULT_REPO_URL),
        help="Git repository URL used with --install-from-git.",
    )
    parser.add_argument(
        "--ref",
        default=os.environ.get("ANSIBLE_RUNNER_REF", DEFAULT_REF),
        help="Git ref used with --install-from-git.",
    )
    parser.add_argument(
        "--wheel-url",
        dest="wheelUrl",
        default=os.environ.get("ANSIBLE_RUNNER_WHEEL_URL", DEFAULT_WHEEL_URL),
        help="Release wheel URL used when --package-spec is not set.",
    )
    parser.add_argument(
        "--install-from-git",
        dest="installFromGit",
        action="store_true",
        default=os.environ.get("ANSIBLE_RUNNER_INSTALL_FROM_GIT") == "1",
        help="Install from the Git repository instead of the release wheel.",
    )
    parser.add_argument(
        "--package-spec",
        dest="packageSpec",
        default=os.environ.get("ANSIBLE_RUNNER_PACKAGE_SPEC"),
        help="Full pip package spec override, for forks or local testing.",
    )
    parser.add_argument(
        "--launcher-name",
        dest="launcherName",
        default=os.environ.get("ANSIBLE_RUNNER_LAUNCHER", DEFAULT_LAUNCHER_NAME),
        help="Project-local launcher filename to write.",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        default=os.environ.get("ANSIBLE_RUNNER_INSTALL_VERBOSE") == "1",
        help="Show venv and pip output instead of writing it only to the log.",
    )
    return parser.parse_args(argv)


def getPackageSpec(args: argparse.Namespace, projectRoot: Path | None = None) -> str:
    """Return the pip package spec for ansibleRunner.

    Args:
        args: Parsed installer arguments.
        projectRoot: Optional project root for local wheel discovery.

    Returns:
        PEP 508 direct reference package spec.
    """

    if args.packageSpec:
        return str(args.packageSpec)
    if not args.installFromGit:
        if projectRoot is not None:
            localWheel = projectRoot / DEFAULT_WHEEL_NAME
            if localWheel.is_file():
                return str(localWheel)
        return f"{PACKAGE_NAME} @ {args.wheelUrl}"
    return f"{PACKAGE_NAME} @ git+{args.repoUrl}@{args.ref}"


def getInstallLogPath(projectRoot: Path) -> Path:
    """Return the project-local installer log path.

    Args:
        projectRoot: Ansible project root.

    Returns:
        Installer log path under ``logs``.
    """

    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    return projectRoot / "logs" / f"ansibleRunner-install-{timestamp}.log"


def ensureVenv(
    venvDir: Path,
    pythonBin: str,
    logPath: Path,
    verbose: bool = False,
) -> bool:
    """Create the project-local virtual environment when missing.

    Args:
        venvDir: Virtual environment directory.
        pythonBin: Python executable used to create the virtual environment.
        logPath: Installer log path.
        verbose: Whether subprocess output should also appear on the terminal.

    Returns:
        True when a virtual environment was created.
    """

    if getVenvPython(venvDir).exists():
        return False
    runLoggedCommand(
        [pythonBin, "-m", "venv", str(venvDir)],
        logPath,
        "Create virtual environment",
        verbose,
    )
    return True


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


def installPackage(
    pythonBin: Path,
    packageSpec: str,
    logPath: Path,
    verbose: bool = False,
) -> None:
    """Install ansibleRunner into the virtual environment.

    Args:
        pythonBin: Virtual environment Python executable.
        packageSpec: Pip package spec to install.
        logPath: Installer log path.
        verbose: Whether subprocess output should also appear on the terminal.
    """

    command = [
        str(pythonBin),
        "-m",
        "pip",
        "install",
        "--upgrade",
        "--disable-pip-version-check",
        packageSpec,
    ]
    runLoggedCommand(command, logPath, "Install ansibleRunner", verbose)


def runLoggedCommand(
    command: list[str],
    logPath: Path,
    title: str,
    verbose: bool = False,
) -> None:
    """Run a subprocess and write command output to the installer log.

    Args:
        command: Command and arguments to run.
        logPath: Installer log path.
        title: Human-readable command title.
        verbose: Whether subprocess output should also appear on the terminal.

    Raises:
        SystemExit: When the command fails.
    """

    logPath.parent.mkdir(parents=True, exist_ok=True)
    with logPath.open("a", encoding="utf-8") as logFile:
        logFile.write(f"## {title}\n")
        logFile.write(f"command={' '.join(command)}\n\n")
        logFile.flush()
        if verbose:
            result = subprocess.run(
                command,
                check=False,
                stderr=subprocess.STDOUT,
                text=True,
            )
        else:
            result = subprocess.run(
                command,
                check=False,
                stderr=subprocess.STDOUT,
                stdout=logFile,
                text=True,
            )
        logFile.write(f"\nexitCode={result.returncode}\n\n")

    if result.returncode != 0:
        print(f"See log: {logPath}", file=sys.stderr)
        raise SystemExit(result.returncode)


def writeLauncher(launcherPath: Path, venvDir: Path) -> None:
    """Write a thin launcher that runs ansibleRunner from the project .venv.

    Args:
        launcherPath: Launcher file to create.
        venvDir: Virtual environment directory.
    """

    launcherPath.write_text(
        getLauncherText(launcherPath.parent, venvDir),
        encoding="utf-8",
    )
    launcherPath.chmod(0o755)


def getLauncherText(projectRoot: Path, venvDir: Path) -> str:
    """Return project launcher source text.

    Args:
        projectRoot: Project root where the launcher is written.
        venvDir: Virtual environment directory.

    Returns:
        Python launcher source code.
    """

    venvExpression = getLauncherVenvExpression(projectRoot, venvDir)
    return f"""#!/usr/bin/env python3
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent
VENV_DIR = {venvExpression}
if os.name == "nt":
    RUNNER = VENV_DIR / "Scripts" / "ansibleRunner.exe"
else:
    RUNNER = VENV_DIR / "bin" / "ansibleRunner"

command = [
    str(RUNNER),
    "--project-root",
    str(PROJECT_ROOT),
    *sys.argv[1:],
]
raise SystemExit(subprocess.run(command, check=False, cwd=PROJECT_ROOT).returncode)
"""


def getLauncherVenvExpression(projectRoot: Path, venvDir: Path) -> str:
    """Return source code for resolving the launcher virtual environment.

    Args:
        projectRoot: Project root where the launcher is written.
        venvDir: Virtual environment directory.

    Returns:
        Python source expression for the launcher.
    """

    try:
        relativeVenv = venvDir.relative_to(projectRoot)
    except ValueError:
        return f"Path({str(venvDir)!r})"
    return f"PROJECT_ROOT / {str(relativeVenv)!r}"


if __name__ == "__main__":
    raise SystemExit(main())
