##############################################################################
# Subprocess-backed Ansible command runner.
#
# USAGE:
#   AnsibleCommandRunner(projectRoot).run(["ansible-playbook", "site.yml"])
#
# OUTPUT VARIABLES:
#   - RunnerResult: Captured command result and derived progress snapshot.
#
# Copyright 2026 Douglas WF Acheson (dwfa@dwfa.ca)
# Licensed under Apache License 2.0. See LICENSE.md for details.
#
# Version: 1.0
# Date: July 05, 2026
##############################################################################

"""Subprocess-backed Ansible command runner."""

from __future__ import annotations

import argparse
import codecs
import errno
import os
import select
import signal
import subprocess
import threading
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import TextIO

from ansibleRunner.defaults import RuntimeDefaults
from ansibleRunner.progress import RunProgress


InputWriter = Callable[[str], bool]
OutputHandler = Callable[[str], None]


@dataclass(frozen=True)
class Pause:
    """Pause marker for chained playbook execution.

    Args:
        message: Message shown before waiting for user input.
    """

    message: str


@dataclass(frozen=True)
class PlaybookRun:
    """Playbook path and default target node for a chain entry.

    Args:
        playbook: Project-relative or absolute playbook path.
        defaultNode: Default Ansible node/group for the playbook.
    """

    playbook: str | Path
    defaultNode: str


@dataclass(frozen=True)
class RunnerOptions:
    """Parsed wrapper-style options for Ansible execution.

    Args:
        debugFlag: Whether to pass ``debugFlag=1`` to Ansible.
        extraArgs: Extra arguments passed through to ``ansible-playbook``.
        node: Optional node override applied to every playbook entry.
        outputLevel: Progress detail level reserved for TUI progress mode.
        syntaxCheck: Whether ``--syntax-check`` was requested.
        testOnly: Test/list flags passed through to ``ansible-playbook``.
    """

    debugFlag: bool = False
    extraArgs: tuple[str, ...] = ()
    node: str | None = None
    outputLevel: str = "role"
    syntaxCheck: bool = False
    testOnly: tuple[str, ...] = ()


@dataclass(frozen=True)
class RunnerResult:
    """Captured result from an Ansible subprocess command.

    Args:
        command: Command and arguments that were executed.
        returnCode: Process return code.
        stdout: Captured standard output.
        stderr: Captured standard error.
        logPath: Optional log path used for streamed playbook output.
    """

    command: tuple[str, ...]
    returnCode: int
    stdout: str
    stderr: str
    logPath: Path | None = None

    @property
    def progress(self) -> RunProgress:
        """Return the progress state derived from the process return code.

        Returns:
            Finished progress snapshot.
        """

        return RunProgress.finished(self.returnCode)


class RunControl:
    """Runtime control for a running subprocess."""

    def __init__(self) -> None:
        """Initialize run cancellation state."""

        self._cancelled = False
        self._cancelProcessGroup = False
        self._inputWriter: InputWriter | None = None
        self._lock = threading.Lock()
        self._process: subprocess.Popen[str] | None = None

    @property
    def cancelled(self) -> bool:
        """Return whether cancellation has been requested.

        Returns:
            True when cancellation has been requested.
        """

        with self._lock:
            return self._cancelled

    def bind(
        self,
        process: subprocess.Popen[str],
        inputWriter: InputWriter | None = None,
        cancelProcessGroup: bool = False,
    ) -> None:
        """Bind the active subprocess to this run control.

        Args:
            cancelProcessGroup: Whether cancellation targets the process group.
            inputWriter: Optional writer for process input.
            process: Process to cancel when requested.
        """

        with self._lock:
            self._cancelProcessGroup = cancelProcessGroup
            self._inputWriter = inputWriter
            self._process = process
            shouldCancel = self._cancelled
        if shouldCancel:
            self.cancel()

    def cancel(self) -> None:
        """Request cancellation of the active process."""

        with self._lock:
            self._cancelled = True
            cancelProcessGroup = self._cancelProcessGroup
            process = self._process
        if process is not None and process.poll() is None:
            if cancelProcessGroup and os.name != "nt":
                try:
                    os.killpg(process.pid, signal.SIGTERM)
                    return
                except (OSError, ProcessLookupError):
                    pass
            process.terminate()

    def clear(self) -> None:
        """Clear the active subprocess after completion."""

        with self._lock:
            self._cancelProcessGroup = False
            self._inputWriter = None
            self._process = None

    def sendInput(self, value: str) -> bool:
        """Send input to the active subprocess.

        Args:
            value: Text to write to subprocess standard input.

        Returns:
            True when the input was sent to a running process.
        """

        with self._lock:
            inputWriter = self._inputWriter
            process = self._process
        if inputWriter is not None:
            return inputWriter(value)
        if process is None or process.poll() is not None or process.stdin is None:
            return False
        try:
            process.stdin.write(value)
            process.stdin.flush()
        except (BrokenPipeError, OSError, ValueError):
            return False
        return True


class AnsibleCommandRunner:
    """Runs Ansible commands from a project root."""

    def __init__(self, projectRoot: Path, logDir: Path | None = None) -> None:
        """Initialize a subprocess runner for a project root.

        Args:
            projectRoot: Directory where commands should be executed.
            logDir: Optional directory for per-playbook run logs.
        """

        self.projectRoot = projectRoot.expanduser().resolve()
        self.logDir = self._resolveLogDir(logDir)

    @staticmethod
    def parseOptions(argv: Sequence[str] | None = None) -> RunnerOptions:
        """Parse wrapper-style arguments into runner options.

        Args:
            argv: Optional command-line arguments excluding the executable name.

        Returns:
            Parsed runner options.
        """

        parser = argparse.ArgumentParser(add_help=True, allow_abbrev=False)
        parser.add_argument(
            "-c",
            action="store_true",
            dest="check",
            help="Pass --check to ansible-playbook.",
        )
        parser.add_argument(
            "-d",
            action="store_true",
            dest="debug",
            help="Pass debugFlag=1 to ansible-playbook.",
        )
        parser.add_argument(
            "-n",
            default=None,
            dest="node",
            help="Override the default node for all playbook entries.",
        )
        parser.add_argument(
            "-s",
            action="store_true",
            dest="syntax",
            help="Pass --syntax-check to ansible-playbook.",
        )
        parser.add_argument(
            "-t",
            action="store_true",
            dest="listTasks",
            help="Pass --list-tasks to ansible-playbook.",
        )
        parser.add_argument(
            "--output-level",
            choices=("play", "role", "task"),
            default="role",
            dest="outputLevel",
            help="Progress detail level for TUI progress mode.",
        )

        namespace, extraArgs = parser.parse_known_args(argv)
        testOnly: list[str] = []
        if namespace.check:
            testOnly.append("--check")
        if namespace.syntax:
            testOnly.append("--syntax-check")
        if namespace.listTasks:
            testOnly.append("--list-tasks")

        return RunnerOptions(
            debugFlag=namespace.debug,
            extraArgs=tuple(extraArgs),
            node=namespace.node,
            outputLevel=namespace.outputLevel,
            syntaxCheck=namespace.syntax,
            testOnly=tuple(testOnly),
        )

    @staticmethod
    def buildPlaybookCommand(
        playbook: str | Path,
        node: str,
        options: RunnerOptions | None = None,
    ) -> tuple[str, ...]:
        """Build the ``ansible-playbook`` command for one playbook.

        Args:
            playbook: Playbook path passed to ``ansible-playbook``.
            node: Effective node/group for the playbook run.
            options: Parsed runner options.

        Returns:
            Command tuple suitable for subprocess execution.
        """

        runnerOptions = options or RunnerOptions()
        extraVars: list[str] = [f"nodes={node}"]
        if runnerOptions.debugFlag:
            extraVars.append("debugFlag=1")
        if runnerOptions.syntaxCheck:
            extraVars.append("newTarget=localhost")

        command: list[str] = ["ansible-playbook"]
        command.extend(runnerOptions.testOnly)
        command.extend(["--extra-vars", " ".join(extraVars)])
        command.extend(runnerOptions.extraArgs)
        command.append(str(playbook))
        return tuple(command)

    def run(self, command: Sequence[str]) -> RunnerResult:
        """Run a command in the configured project root.

        Args:
            command: Command and arguments to execute.

        Returns:
            Captured command result.
        """

        completed = subprocess.run(
            list(command),
            cwd=self.projectRoot,
            check=False,
            text=True,
            capture_output=True,
        )
        return RunnerResult(
            command=tuple(command),
            returnCode=completed.returncode,
            stdout=completed.stdout,
            stderr=completed.stderr,
        )

    def runChain(
        self,
        entries: Sequence[PlaybookRun | Pause | tuple[str | Path, str]],
        argv: Sequence[str] | None = None,
        progressMode: bool = False,
    ) -> int:
        """Run a playbook chain, stopping on the first failure.

        Args:
            entries: Playbook entries and pauses to process in order.
            argv: Optional runner arguments excluding the executable name.
            progressMode: Reserved for future TUI progress rendering.

        Returns:
            Zero on success, otherwise the first non-zero return code.
        """

        options = self.parseOptions(argv)
        for entry in entries:
            if isinstance(entry, Pause):
                try:
                    input(f"\n{entry.message}\nPress Enter to continue...")
                except KeyboardInterrupt:
                    return 130
                continue

            playbookRun = self._coercePlaybookRun(entry)
            result = self.runPlaybook(
                playbookRun.playbook,
                playbookRun.defaultNode,
                options,
                progressMode,
            )
            if result.returnCode != 0:
                return result.returnCode
        return 0

    def runPlaybook(
        self,
        playbook: str | Path,
        defaultNode: str,
        options: RunnerOptions | None = None,
        progressMode: bool = False,
        outputHandler: OutputHandler | None = None,
        echoOutput: bool = True,
        runControl: RunControl | None = None,
    ) -> RunnerResult:
        """Run one project playbook with wrapper-style Ansible defaults.

        Args:
            playbook: Project-relative or absolute playbook path.
            defaultNode: Default node/group used when no override is provided.
            options: Parsed runner options.
            progressMode: Reserved for future TUI progress rendering.
            outputHandler: Optional callback for each merged output line.
            echoOutput: Whether to echo merged output to stdout.
            runControl: Optional process cancellation control.

        Returns:
            Captured playbook run result.
        """

        del progressMode

        runnerOptions = options or RunnerOptions()
        node = runnerOptions.node or defaultNode
        if not node:
            return RunnerResult(
                command=(),
                returnCode=1,
                stderr=(
                    f"ERROR: no node for [{playbook}] -- entry has no default "
                    "and -n <node> was not given"
                ),
                stdout="",
            )

        playbookPath = self._resolvePlaybookPath(playbook)
        if not playbookPath.is_file():
            return RunnerResult(
                command=(),
                returnCode=1,
                stderr=f"ERROR: file not found [{playbook}]!",
                stdout="",
            )

        logPath = self._buildLogPath(playbookPath)
        command = self.buildPlaybookCommand(playbook, node, runnerOptions)
        env = self._buildEnv(runnerOptions)

        self._writeOutput(
            f"Running {Path(playbook).stem} playbook ...\n",
            outputHandler,
            echoOutput,
        )
        self._writeOutput(f"Logging to {logPath}\n", outputHandler, echoOutput)

        returnCode = self._execAndTee(
            command,
            env,
            logPath,
            outputHandler,
            echoOutput,
            runControl,
        )
        self._pruneRunLogs(playbookPath, logPath)
        return RunnerResult(
            command=command,
            returnCode=returnCode,
            stderr="",
            stdout="",
            logPath=logPath,
        )

    def _buildEnv(self, options: RunnerOptions) -> dict[str, str]:
        """Build the environment for an Ansible subprocess.

        Args:
            options: Parsed runner options.

        Returns:
            Environment mapping for subprocess execution.
        """

        env = dict(os.environ)
        env["PYTHONUNBUFFERED"] = "1"
        if not options.debugFlag:
            env["ANSIBLE_DISPLAY_SKIPPED_HOSTS"] = "false"
        return env

    def _buildLogPath(self, playbookPath: Path) -> Path:
        """Build a timestamped log path for a playbook.

        Args:
            playbookPath: Resolved playbook path.

        Returns:
            Log file path under the runner log directory.
        """

        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        return self.logDir / f"{playbookPath.stem}-{timestamp}.log"

    def _pruneRunLogs(
        self,
        playbookPath: Path,
        activeLogPath: Path,
        keepCount: int = 5,
    ) -> None:
        """Keep only the newest run logs for a playbook.

        Args:
            playbookPath: Playbook whose run logs should be pruned.
            activeLogPath: Current run log path, which must be retained.
            keepCount: Number of newest run logs to keep.
        """

        logs = sorted(
            self.logDir.glob(f"{playbookPath.stem}-*.log"),
            key=lambda path: (path.stat().st_mtime, path.name),
            reverse=True,
        )
        activeResolved = activeLogPath.resolve()
        for logPath in logs[keepCount:]:
            if logPath.resolve() == activeResolved:
                continue
            try:
                logPath.unlink()
            except FileNotFoundError:
                continue

    @staticmethod
    def _coercePlaybookRun(
        entry: PlaybookRun | tuple[str | Path, str],
    ) -> PlaybookRun:
        """Normalize a playbook chain entry.

        Args:
            entry: PlaybookRun object or compatible tuple.

        Returns:
            Normalized playbook run entry.
        """

        if isinstance(entry, PlaybookRun):
            return entry
        playbook, defaultNode = entry
        return PlaybookRun(playbook=playbook, defaultNode=defaultNode)

    def _execAndTee(
        self,
        command: Sequence[str],
        env: dict[str, str],
        logPath: Path,
        outputHandler: OutputHandler | None = None,
        echoOutput: bool = True,
        runControl: RunControl | None = None,
    ) -> int:
        """Execute a command and tee merged output to stdout and a log.

        Args:
            command: Command and arguments to execute.
            env: Environment for the subprocess.
            logPath: File where merged output should be written.
            outputHandler: Optional callback for each merged output line.
            echoOutput: Whether to echo merged output to stdout.
            runControl: Optional process cancellation control.

        Returns:
            Subprocess return code.
        """

        logPath.parent.mkdir(parents=True, exist_ok=True)
        if os.name != "nt":
            return self._execAndTeePty(
                command,
                env,
                logPath,
                outputHandler,
                echoOutput,
                runControl,
            )

        with logPath.open("w", encoding="utf-8") as logFile:
            process = subprocess.Popen(
                list(command),
                cwd=self.projectRoot,
                env=env,
                stderr=subprocess.STDOUT,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                text=True,
            )
            if runControl is not None:
                runControl.bind(process)
            assert process.stdout is not None
            self._teeOutput(process.stdout, logFile, outputHandler, echoOutput)
            process.stdout.close()
            returnCode = process.wait()
            if runControl is not None:
                runControl.clear()
                if runControl.cancelled:
                    return 130
            return returnCode

    def _execAndTeePty(
        self,
        command: Sequence[str],
        env: dict[str, str],
        logPath: Path,
        outputHandler: OutputHandler | None = None,
        echoOutput: bool = True,
        runControl: RunControl | None = None,
    ) -> int:
        """Execute a command through a PTY and tee merged output.

        Args:
            command: Command and arguments to execute.
            env: Environment for the subprocess.
            logPath: File where merged output should be written.
            outputHandler: Optional callback for each merged output line.
            echoOutput: Whether to echo merged output to stdout.
            runControl: Optional process cancellation and input control.

        Returns:
            Subprocess return code.
        """

        import pty
        import fcntl
        import termios

        masterFd, slaveFd = pty.openpty()

        def prepareChildPty() -> None:
            """Make the PTY slave the child process controlling terminal."""

            os.setsid()
            fcntl.ioctl(slaveFd, termios.TIOCSCTTY, 0)

        def writeInput(value: str) -> bool:
            """Write input to the PTY master file descriptor."""

            try:
                os.write(masterFd, value.encode("utf-8"))
            except OSError:
                return False
            return True

        with logPath.open("w", encoding="utf-8") as logFile:
            process = subprocess.Popen(
                list(command),
                close_fds=True,
                cwd=self.projectRoot,
                env=env,
                preexec_fn=prepareChildPty,
                stderr=slaveFd,
                stdin=slaveFd,
                stdout=slaveFd,
            )
            os.close(slaveFd)
            if runControl is not None:
                runControl.bind(
                    process,
                    writeInput,
                    cancelProcessGroup=True,
                )
            try:
                self._teePtyOutput(
                    masterFd,
                    process,
                    logFile,
                    outputHandler,
                    echoOutput,
                )
                returnCode = process.wait()
            finally:
                if runControl is not None:
                    runControl.clear()
                try:
                    os.close(masterFd)
                except OSError:
                    pass

        if runControl is not None and runControl.cancelled:
            return 130
        return returnCode

    def _resolvePlaybookPath(self, playbook: str | Path) -> Path:
        """Resolve a playbook path for filesystem validation.

        Args:
            playbook: Project-relative or absolute playbook path.

        Returns:
            Absolute playbook path.
        """

        playbookPath = Path(playbook)
        if playbookPath.is_absolute():
            return playbookPath
        return self.projectRoot / playbookPath

    def _resolveLogDir(self, logDir: Path | None) -> Path:
        """Resolve the log directory for playbook execution.

        Args:
            logDir: Optional caller-supplied log directory.

        Returns:
            Resolved log directory path.
        """

        if logDir is not None:
            return logDir.expanduser()
        envLogDir = os.environ.get("LOG_DIR")
        if envLogDir:
            return Path(envLogDir).expanduser()
        return RuntimeDefaults.forProject(self.projectRoot).logDir

    @staticmethod
    def _cleanPtyText(text: str) -> str:
        """Normalize PTY text before logging or parsing.

        Args:
            text: Raw decoded PTY text.

        Returns:
            Text with carriage returns normalized.
        """

        return text.replace("\r\n", "\n").replace("\r", "\n")

    def _emitOutput(
        self,
        text: str,
        logFile: TextIO,
        outputHandler: OutputHandler | None = None,
        echoOutput: bool = True,
    ) -> None:
        """Emit output to stdout, a log file, and an optional callback.

        Args:
            text: Text to emit.
            logFile: Writable log file stream.
            outputHandler: Optional callback for output text.
            echoOutput: Whether to echo output to stdout.
        """

        if echoOutput:
            print(text, end="")
        logFile.write(text)
        logFile.flush()
        if outputHandler is not None:
            outputHandler(text)

    def _teePtyOutput(
        self,
        masterFd: int,
        process: subprocess.Popen[bytes],
        logFile: TextIO,
        outputHandler: OutputHandler | None = None,
        echoOutput: bool = True,
    ) -> None:
        """Read PTY output and tee complete lines.

        Args:
            masterFd: PTY master file descriptor.
            process: Running subprocess.
            logFile: Writable log file stream.
            outputHandler: Optional callback for each output line.
            echoOutput: Whether to echo merged output to stdout.
        """

        decoder = codecs.getincrementaldecoder("utf-8")(errors="replace")
        outputBuffer = ""
        while True:
            if process.poll() is not None:
                ready, _, _ = select.select([masterFd], [], [], 0)
                if not ready:
                    break
            else:
                ready, _, _ = select.select([masterFd], [], [], 0.1)
                if not ready:
                    continue

            try:
                raw = os.read(masterFd, 4096)
            except OSError as error:
                if error.errno == errno.EIO:
                    break
                raise
            if not raw:
                break

            outputBuffer += self._cleanPtyText(decoder.decode(raw))
            while "\n" in outputBuffer:
                line, outputBuffer = outputBuffer.split("\n", 1)
                self._emitOutput(
                    f"{line}\n",
                    logFile,
                    outputHandler,
                    echoOutput,
                )

        outputBuffer += self._cleanPtyText(decoder.decode(b"", final=True))
        if outputBuffer:
            self._emitOutput(outputBuffer, logFile, outputHandler, echoOutput)

    @staticmethod
    def _teeOutput(
        source: TextIO,
        logFile: TextIO,
        outputHandler: OutputHandler | None = None,
        echoOutput: bool = True,
    ) -> None:
        """Write subprocess output to stdout and a log file.

        Args:
            source: Text stream from the subprocess.
            logFile: Writable log file stream.
            outputHandler: Optional callback for each merged output line.
            echoOutput: Whether to echo merged output to stdout.
        """

        for line in source:
            if echoOutput:
                print(line, end="")
            logFile.write(line)
            logFile.flush()
            if outputHandler is not None:
                outputHandler(line)

    @staticmethod
    def _writeOutput(
        line: str,
        outputHandler: OutputHandler | None,
        echoOutput: bool,
    ) -> None:
        """Write runner status output to stdout and optional handler.

        Args:
            line: Output line to emit.
            outputHandler: Optional callback for the output line.
            echoOutput: Whether to echo the line to stdout.
        """

        if echoOutput:
            print(line, end="")
        if outputHandler is not None:
            outputHandler(line)
