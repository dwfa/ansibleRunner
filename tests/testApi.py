##############################################################################
# Package API tests for ansibleRunner.
#
# USAGE:
#   python3 -m pytest tests/test_api.py
#
# WORKFLOW:
#   1. Verify the public main entry point accepts a project root.
#   2. Verify runtime defaults remain project-local.
#
# Copyright 2026 Douglas WF Acheson (dwfa@dwfa.ca)
# Licensed under Apache License 2.0. See LICENSE.md for details.
#
# Version: 1.0
# Date: July 05, 2026
##############################################################################

from pathlib import Path

from ansibleRunner import main
from ansibleRunner.defaults import RuntimeDefaults


def testMainAcceptsProjectRootAndArgv(tmp_path, capsys):
    """Verify the public API accepts a project root and argument list."""

    result = main(tmp_path, ["--list-defaults"])

    assert result == 0
    output = capsys.readouterr().out
    assert f"projectRoot={tmp_path.resolve()}" in output
    assert f"logDir={tmp_path.resolve() / '.ansibleRunner' / 'logs'}" in output


def testRuntimeDefaultsAreProjectLocal(tmp_path):
    """Verify runtime defaults stay under the supplied project root."""

    defaults = RuntimeDefaults.forProject(Path(tmp_path))

    assert defaults.projectRoot == tmp_path.resolve()
    assert defaults.logDir == tmp_path.resolve() / ".ansibleRunner" / "logs"
    assert defaults.stateDir == tmp_path.resolve() / ".ansibleRunner" / "state"
