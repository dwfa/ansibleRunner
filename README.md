<!--
##############################################################################
# ansibleRunner
#
# Package overview, installation notes, CLI usage, and wheel build workflow.
#
# Copyright 2026 Douglas WF Acheson (dwfa@dwfa.ca)
# Licensed under Apache License 2.0. See LICENSE.md for details.
#
# Version: 1.0
# Date: July 05, 2026
##############################################################################
-->

# ansibleRunner

`ansibleRunner` is a standalone Python package for reusable TUI and Ansible
runner behavior that was first prototyped in `rpiMgmt`.

The package name intentionally uses `ansibleRunner` instead of
`ansible-runner` to avoid colliding with the existing Ansible ecosystem
project of that name.

## Goals

- Own menu and application flow for project-local management tools.
- Own runner and progress reporting logic for Ansible commands.
- Own prompt handling and validation.
- Provide sensible logs and state defaults.
- Expose a public API that thin wrappers can call:

```python
from ansibleRunner import main

raise SystemExit(main(projectRoot, argv))
```

The future `rpiMgmt` wrapper should only discover its project root and pass
`projectRoot` plus `argv` into this package.

## Installation

Install from GitHub:

```shell
python3 -m pip install "ansibleRunner @ git+https://github.com/dwfa/ansibleRunner.git"
```

Install from a local checkout for testing:

```shell
python3 -m pip install .
```

For editable local development:

```shell
python3 -m pip install -e ".[dev]"
```

## CLI

After installation:

```shell
ansibleRunner --project-root /path/to/project
```

With no diagnostic flag, `ansibleRunner` opens the Textual playbook menu for
the selected project root.

To print resolved project defaults without opening the TUI:

```shell
ansibleRunner --project-root /path/to/project --list-defaults
```

For local development:

```shell
python3 -m ansibleRunner --project-root /path/to/project --list-defaults
```

## Standalone Project Shim

For quick end-to-end testing inside an Ansible project, copy or symlink the
standalone shim:

```shell
cp tests/endToEnd/ansibleRunnerShim.py /path/to/ansible/project/runAnsible.py
chmod +x /path/to/ansible/project/runAnsible.py
```

Or link it back to this checkout:

```shell
ln -s /path/to/ansibleRunner/tests/endToEnd/ansibleRunnerShim.py \
  /path/to/ansible/project/runAnsible.py
```

Run it from the Ansible project root:

```shell
cd /path/to/ansible/project
./runAnsible.py --list-defaults
```

The shim treats the current working directory as the project root, bootstraps
`ansibleRunner` into `.venv`, installs from this repository's test wheel, then
runs:

```shell
.venv/bin/python -m ansibleRunner --project-root "$PWD" ...
```

Build the wheel with `./scripts/build.py` before testing the shim.

## Build Check

Build a local wheel distribution:

```shell
./scripts/build.py
```
