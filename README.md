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
curl -LO https://github.com/dwfa/ansibleRunner/releases/latest/download/install.py
python3 install.py
```

The installer creates `.venv`, installs `ansibleRunner`, installs runtime
dependencies including `ansible-core`, and writes `ar.py` as a thin project
launcher.

Package source selection:

- `python3 install.py -w ./ansiblerunner-<version>-py3-none-any.whl` installs
  the explicit wheel you provide.
- If no `-w` value is provided, the installer looks beside `install.py` for
  `ansiblerunner-*-py3-none-any.whl` and uses the newest version found there.
- If no local wheel is found, the installer downloads the newest release wheel
  from GitHub release assets.

Start the TUI from the Ansible project root:

```shell
./ar.py
```

Convenience forms:

```shell
curl -fsSL https://github.com/dwfa/ansibleRunner/releases/latest/download/install.py | python3 -
```

```shell
python3 <(curl -fsSL https://github.com/dwfa/ansibleRunner/releases/latest/download/install.py)
```

If GitHub release downloads are blocked on the target machine, download both
release files on a machine that has access, copy them to the Ansible project
root, then run the installer there. The wheel asset is the file named like
`ansiblerunner-<version>-py3-none-any.whl` on the
[latest release](https://github.com/dwfa/ansibleRunner/releases/latest):

```shell
curl -LO https://github.com/dwfa/ansibleRunner/releases/latest/download/install.py
```

Then place the downloaded wheel beside `install.py`.

```shell
python3 install.py
```

When multiple `ansiblerunner-*-py3-none-any.whl` files are beside
`install.py`, the installer chooses by parsed package version, not file date.

The local wheel covers `ansibleRunner` itself. Pip still needs access to
runtime dependencies such as `ansible-core` and `textual` through its cache, a
company PyPI mirror, or another configured package source.

You can also point the installer at a specific local wheel:

```shell
python3 install.py -w ./ansiblerunner-<version>-py3-none-any.whl
```

`-w` and `--whl` are shorthand for `--package-spec`. Use `--package-spec`
directly when you want to pass a full custom pip package spec, such as a fork,
checkout, or test artifact.

Install the package directly from a downloaded wheel:

```shell
python3 -m pip install ./ansiblerunner-<version>-py3-none-any.whl
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

- `playbooks/`: playbook menu root. Direct child directories are shown first
  for grouping, followed by direct child `*.yaml` and `*.yml` playbooks.
  Press `Enter` on a directory to open it.
- The first meaningful `# ...` comment near the top of a playbook is shown as
  the playbook title. If no title exists, the TUI shows `(no title)`.
- A saved `Node` value or launch-time `-n <node>` value is optional. When set,
  the runner passes that target through to Ansible as `nodes=<value>`. When
  unset, the playbook is run without a `nodes` extra-var and can use its own
  `hosts`, inventory, or variables.
- Every run receives `playbookPath` as an extra-var for project wrappers that
  include files relative to the `playbooks/` root. Direct child playbooks get
  `playbookPath=./`; a playbook one directory down, such as
  `playbooks/db/listServers-pb.yaml`, gets `playbookPath=../`.
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
  settings. Nested playbooks use a path-aware key such as
  `db/listServers-pb`.
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

The first screen lists directories and playbooks from `playbooks/`.

- Use `Up` and `Down` to move.
- Press `Enter` on a directory to open it.
- Press `Enter` on a playbook to review and run it.
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

## AR Display Hints

Task, role, and play names may include `@ar:hide` when a row should be omitted
from the AR progress tree while still running normally under Ansible.

Examples:

```yaml
- name: "load temporary vars @ar:hide"
  ansible.builtin.include_vars:
    file: temp.yaml
```

Display rules:

- AR strips `@ar:hide` from matching and display names.
- A hidden task suppresses that task row. For `niceDisplay`, this is how the
  wrapper task becomes only the boxed output block.
- A hidden role suppresses the role row when Ansible's emitted role segment
  contains `@ar:hide`; visible child tasks can still render.
- A hidden play suppresses the play row; visible child roles/tasks can still
  render.
- Completed `niceWait` and `niceInput` prompt history rows are AR interaction
  records, not Ansible task rows. They remain visible unless prompt-history
  hiding is added separately.
- Plain `ansible-playbook` still shows the literal task name, including the
  hint.

## Special TUI Wrappers

`ansibleRunner` can recognize small Ansible wrapper task files and render them
as cleaner TUI prompts or display blocks. The wrappers are optional. A playbook
can still run with normal `ansible-playbook`; the wrapper task names simply give
AR a stable title to read from Ansible output and callback events. Detection is
based on the included wrapper filename, so the files may live wherever a
project keeps shared tasks.

### Prompt Wrappers

Use `niceWait.yaml` for continue prompts and `niceInput.yaml` for text
input prompts. In the playbook, include the wrapper file and pass:

- `title`: short label shown by AR.
- `data`: full prompt text shown by Ansible and AR; multiline text is allowed.

Playbook usage:

```yaml
- name: "Confirm delete"
  ansible.builtin.include_tasks: "path/to/niceWait.yaml"
  vars:
    title: "Confirm delete"
    data: |
      About to DELETE server [example-db-01] in env [dev].
      Press Enter to continue.
```

```yaml
- name: "Enter server alias"
  ansible.builtin.include_tasks: "path/to/niceInput.yaml"
  vars:
    title: "Enter server alias"
    data: |
      Enter the short server alias to use for this run.
```

Prompt display rules:

- The reusable wrapper task uses `niceWait:` or `niceInput:` in its own task
  name so AR can read the title from Ansible output.
- The prompt panel shows `title` in its heading and `data` as the prompt body.
- `niceWait.yaml` is treated as a continue prompt; `niceInput.yaml` is
  treated as a text prompt.
- Native Ansible prompt text from the run log wins when present.
- Multiline prompt text is preserved in the input panel.
- The internal wrapper task rows are hidden from the progress tree.
- Completed prompt interactions remain visible in normal role/task progress.

### niceDisplay

Use `niceDisplay.yaml` when a task should render a boxed display block instead
of a normal task row. In the playbook, include the wrapper file and pass:

- `title`: short box title shown by AR.
- `data`: display payload printed by Ansible and rendered by AR. A string,
  multiline block, list, or mapping can be used.

Playbook usage:

```yaml
- name: "Show deprovision result"
  ansible.builtin.include_tasks: "path/to/niceDisplay.yaml"
  vars:
    title: "deprovisionDB complete"
    data:
      - "server = [example-db-01.postgres.database.example.com]"
      - "env    = [dev]"
      - "action = [deleted]"
```

Display rules:

- The reusable wrapper task uses `niceDisplay:` in its own task name so AR can
  read the title from Ansible output.
- The include row and internal display task row are hidden.
- Only the boxed title and payload are shown.
- `niceDisplay:` is stripped from the boxed title.
- At `--output-level role`, ordinary task rows remain hidden.
- If the same role has completed prompt interactions, those prompt rows are not
  appended below the boxed display block.
- Press `y` to copy the full boxed output block.

### Wrapper Task Files

These are the reusable task files included by the playbook examples above.
Projects can copy and adapt them wherever shared task files live.

`niceWait.yaml`:

```yaml
---
- name: "niceWait: {{ title | default('wait for user input') }}"
  ansible.builtin.pause:
    prompt: "{{ data | default(title | default('Press Enter to continue')) }}"
    echo: true
```

`niceInput.yaml`:

```yaml
---
- name: "niceInput: {{ title | default('prompt for user input') }}"
  ansible.builtin.pause:
    prompt: "{{ data | default(title | default('Enter value')) }}"
    echo: true
  register: promptInput

- name: "set prompted value"
  ansible.builtin.set_fact:
    promptValue: "{{ promptInput.user_input | default('') }}"
```

`niceDisplay.yaml`:

```yaml
---
- name: "niceDisplay: {{ title | default('display output') }}"
  ansible.builtin.debug:
    msg: "{{ data }}"
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
