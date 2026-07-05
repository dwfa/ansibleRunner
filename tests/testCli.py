##############################################################################
# Command-line entry point tests for ansibleRunner.
#
# USAGE:
#   python3 -m pytest tests/test_cli.py
#
# WORKFLOW:
#   1. Verify the CLI uses the current working directory by default.
#
# Copyright 2026 Douglas WF Acheson (dwfa@dwfa.ca)
# Licensed under Apache License 2.0. See LICENSE.md for details.
#
# Version: 1.0
# Date: July 05, 2026
##############################################################################

from ansibleRunner import cli


def testCliUsesCurrentDirectoryByDefault(tmp_path, monkeypatch, capsys):
    """Verify the CLI uses the current working directory by default."""

    monkeypatch.chdir(tmp_path)

    result = cli.main(["--list-defaults"])

    assert result == 0
    assert f"projectRoot={tmp_path.resolve()}" in capsys.readouterr().out
