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

raise SystemExit(main(project_root, argv))
```

The future `rpiMgmt` wrapper should only discover its project root and pass
`project_root` plus `argv` into this package.

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
ansibleRunner --project-root /path/to/project --list-defaults
```

For local development:

```shell
python3 -m ansibleRunner --project-root /path/to/project --list-defaults
```

## Build Check

Build a local wheel distribution:

```shell
./scripts/build.py
```
