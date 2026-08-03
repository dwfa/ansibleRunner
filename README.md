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

`ansibleRunner` gives Ansible project maintainers a project-local terminal UI
for selecting playbooks, configuring run arguments, answering prompts, and
watching live task progress with useful logs.

It is packaged as reusable Python tooling so each Ansible project can keep only
a thin launcher in its repository while sharing the same menu, runner, prompt,
progress, state, and logging behavior.

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

Project wrappers should stay thin: discover the project root, pass through CLI
arguments, and let `ansibleRunner` own the shared behavior.

## Installation

For a project-local install, download the Python installer from GitHub, inspect
it if desired, then run it from the Ansible project root:

```shell
curl -O https://raw.githubusercontent.com/dwfa/ansibleRunner/v1.0.0/install.py
python3 install.py
```

The installer creates `.venv`, installs `ansibleRunner` from GitHub, and writes
`ansibleRunner.py` as a thin project launcher.

Start the TUI from the Ansible project root:

```shell
./ansibleRunner.py
```

Convenience forms:

```shell
curl -fsSL https://raw.githubusercontent.com/dwfa/ansibleRunner/v1.0.0/install.py | python3 -
```

```shell
python3 <(curl -fsSL https://raw.githubusercontent.com/dwfa/ansibleRunner/v1.0.0/install.py)
```

Install the package directly from GitHub:

```shell
python3 -m pip install "ansibleRunner @ git+https://github.com/dwfa/ansibleRunner.git@v1.0.0"
```

Install from a local checkout for testing:

```shell
python3 -m pip install .
```

For editable local development:

```shell
python3 -m pip install -e ".[dev]"
```

## Project Layout

`ansibleRunner` treats the directory containing `ansibleRunner.py` as the
Ansible project root.

Expected project files:

- `playbooks/*.yaml` or `playbooks/*.yml`: top-level playbooks shown in the
  TUI. Nested files are ignored.
- The first meaningful `# ...` comment near the top of a playbook is shown as
  the playbook title. If no title exists, the TUI shows `(no title)`.
- `ansible-playbook`: must be available on `PATH` when a playbook is run.

Files created by the installer:

- `.venv/`: project-local Python virtual environment.
- `ansibleRunner.py`: project-local launcher. This file knows the project root,
  so normal project usage does not require `--project-root`.
- `logs/ansibleRunner-install-<timestamp>.log`: installer details, including
  virtual environment and pip output.

Files created while using the TUI:

- `.ansibleRunner/state/playbookConfig.json`: saved per-playbook launch
  settings.
- `logs/<playbook>-<timestamp>.log`: native Ansible log for each run.
- `logs/<playbook>-<timestamp>.events.jsonl`: structured Ansible callback
  events used by the TUI to track active plays, roles, tasks, and prompts.

Run logs are pruned per playbook, keeping the most recent five `.log` files and
their matching `.events.jsonl` files.

## TUI Usage

Start the project launcher:

```shell
./ansibleRunner.py
```

The first screen lists playbooks from `playbooks/`.

- Use `Up` and `Down` to move.
- Press `Enter` to review and run the selected playbook.
- Press `c` to edit saved settings for the selected playbook.
- Press `q` or `Esc` to quit.

The launch screen shows the exact Ansible arguments that will be used.

- Press `Enter` or `r` to run.
- Press `e` to edit settings for this run only.
- Press `c` to edit and save settings for future runs.
- Press `q` or `Esc` to return to the playbook list.

The configure screen supports:

- `Node`: passed as `-n <node>`.
- `Output level`: `play`, `role`, or `task`.
- `Debug`: passed as `-d`.
- `Check`: passed as `-c`.
- `Syntax check`: passed as `-s`.
- `List tasks`: passed as `-t`.
- `Ansible arguments`: extra raw arguments, available from edit-once launch
  configuration.

Use `Left` and `Right` to change choice/boolean fields, `Enter` to edit text
fields, `s` to save or apply, and `q`/`Esc` to go back.

The run screen shows live progress and handles supported Ansible prompts inside
the progress panel.

- Press `Enter` or `Space` to continue through a continue prompt.
- Type a value and press `Enter` for text prompts.
- Press `c` or `Esc` to cancel the active run.
- Press `Ctrl-Z` to suspend.
- Scroll up to inspect earlier progress; auto-follow resumes when you scroll
  back to the bottom.

## Direct CLI

When using the project launcher, do not pass `--project-root`; the launcher
sets it for you.

Use `--project-root` only when invoking the installed package directly, outside
a project launcher:

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
