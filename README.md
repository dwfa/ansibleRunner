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
curl -LO https://github.com/dwfa/ansibleRunner/releases/download/v1.0.4/install.py
python3 install.py
```

The installer creates `.venv`, installs the `ansibleRunner` release wheel from
GitHub, installs runtime dependencies including `ansible-core`, and writes
`ar.py` as a thin project launcher.

Start the TUI from the Ansible project root:

```shell
./ar.py
```

Convenience forms:

```shell
curl -fsSL https://github.com/dwfa/ansibleRunner/releases/download/v1.0.4/install.py | python3 -
```

```shell
python3 <(curl -fsSL https://github.com/dwfa/ansibleRunner/releases/download/v1.0.4/install.py)
```

If GitHub release downloads are blocked on the target machine, download both
release files on a machine that has access, copy them to the Ansible project
root, then run the installer there:

```shell
curl -LO https://github.com/dwfa/ansibleRunner/releases/download/v1.0.4/install.py
curl -LO https://github.com/dwfa/ansibleRunner/releases/download/v1.0.4/ansiblerunner-1.0.4-py3-none-any.whl
```

```shell
python3 install.py
```

When `ansiblerunner-1.0.4-py3-none-any.whl` is beside `install.py`, the
installer uses that local wheel instead of downloading it from GitHub.

The local wheel covers `ansibleRunner` itself. Pip still needs access to
runtime dependencies such as `ansible-core` and `textual` through its cache, a
company PyPI mirror, or another configured package source.

You can also point the installer at a specific local wheel:

```shell
python3 install.py --package-spec ./ansiblerunner-1.0.4-py3-none-any.whl
```

Install the package directly from GitHub:

```shell
python3 -m pip install "ansibleRunner @ https://github.com/dwfa/ansibleRunner/releases/download/v1.0.4/ansiblerunner-1.0.4-py3-none-any.whl"
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

`ansibleRunner` treats the directory containing `ar.py` as the
Ansible project root.

Expected project files:

- `playbooks/*.yaml` or `playbooks/*.yml`: top-level playbooks shown in the
  TUI. Nested files are ignored.
- The first meaningful `# ...` comment near the top of a playbook is shown as
  the playbook title. If no title exists, the TUI shows `(no title)`.
- A saved `Node` value or launch-time `-n <node>` value is optional. When set,
  the runner passes that target through to Ansible as `nodes=<value>`. When
  unset, the playbook is run without a `nodes` extra-var and can use its own
  `hosts`, inventory, or variables.
- `ansible-core` is installed into `.venv`, so `ar.py` uses the project-local
  `ansible-playbook` command. Project-specific collections, roles, inventory,
  and Ansible configuration remain owned by the Ansible project.

Files created by the installer:

- `.venv/`: project-local Python virtual environment.
- `ar.py`: project-local launcher. This file knows the project root,
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
./ar.py
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

- `Node`: optional target passed as `-n <node>` and then to Ansible as
  `nodes=<value>`. Leave it unset for playbooks that define their own `hosts`
  or do not use the `nodes` extra-var.
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
- After a run completes, press `Enter`, `Space`, or `Esc` to return to the
  launch screen.
- Tasks named `niceDisplay: <title>` render their `msg` payload as a boxed
  display block. The internal `niceDisplay:` task row is hidden from the
  progress tree.
- When boxed display output is visible, press `y` to copy the full block, or
  use `Fn`-drag selection followed by `⌘C` to copy selected text in terminals
  that support it.

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
