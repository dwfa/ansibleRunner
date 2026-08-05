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
- When boxed display output is visible, press `y` to copy the full block, or
  use `Fn`-drag selection followed by `⌘C` to copy selected text in terminals
  that support it.

## Special TUI Wrappers

`ansibleRunner` recognizes a few project conventions as display hints. These
conventions are optional Ansible patterns for projects that want cleaner TUI
output without changing normal Ansible execution.

### Prompt Wrappers

Use `waitForInput.yaml` for continue prompts and `promptForInput.yaml` for text
input prompts. The wrapper task name can be whatever reads well in the playbook;
the include target and native Ansible prompt text determine how the TUI handles
the prompt. The wrapper files can live wherever the Ansible project keeps
shared task files.

```yaml
- name: "Confirm delete"
  ansible.builtin.include_tasks: "path/to/waitForInput.yaml"
  vars:
    title: "Confirm delete"
    prompt: |
      About to DELETE server [example-db-01] in env [dev].
      Press Enter to continue.
```

```yaml
- name: "Enter server alias"
  ansible.builtin.include_tasks: "path/to/promptForInput.yaml"
  vars:
    title: "Enter server alias"
    prompt: |
      Enter the short server alias to use for this run.
```

Prompt display rules:

- `title:` is the short fallback label for the prompt.
- `prompt:` is the full prompt body and may be multiline.
- Native Ansible prompt text from the run log wins when present.
- Multiline prompt text is preserved in the input panel.
- The internal `wait for user input` / `prompt for user input` implementation
  task rows are hidden from the progress tree.
- Completed prompt interactions remain visible in normal role/task progress,
  unless the same role later renders a boxed `niceDisplay` block.

### niceDisplay

Use `niceDisplay.yaml` when a task should show display output as a boxed block
instead of a normal task row. The wrapper task name becomes the fallback box
title.

```yaml
- name: "deprovisionDB complete"
  ansible.builtin.include_tasks: "path/to/niceDisplay.yaml"
  vars:
    title: "deprovisionDB complete"
    msg: |
      server = [example-db-01.postgres.database.example.com]
      env    = [dev]
      action = [deleted]
```

Display rules:

- The wrapper include row and internal display task row are hidden.
- Only the boxed title and payload are shown.
- At `--output-level role`, ordinary task rows remain hidden.
- If the same role has completed prompt interactions, those prompt rows are not
  appended below the boxed display block.
- Press `y` to copy the full boxed output block.

### Wrapper Task Files

These are minimal wrapper task file examples that projects can copy and adapt.

`waitForInput.yaml`:

```yaml
---
- name: "wait for user input"
  ansible.builtin.pause:
    prompt: "{{ prompt | default(title | default('Press Enter to continue')) }}"
    echo: true
```

`promptForInput.yaml`:

```yaml
---
- name: "prompt for user input"
  ansible.builtin.pause:
    prompt: "{{ prompt | default(title | default('Enter value')) }}"
    echo: true
  register: promptInput

- name: "set prompted value"
  ansible.builtin.set_fact:
    promptValue: "{{ promptInput.user_input | default('') }}"
```

`niceDisplay.yaml`:

```yaml
---
- name: "show display output"
  ansible.builtin.debug:
    msg: "{{ msg | default(display | default(body | default(''))) }}"
```

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
