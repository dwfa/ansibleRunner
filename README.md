<!--
##############################################################################
# ansibleRunner
#
# Concise package overview, quickstart, and documentation index.
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
a thin launcher while sharing the same menu, runner, prompt, progress, state,
and logging behavior.

The package name intentionally uses `ansibleRunner` instead of
`ansible-runner` to avoid colliding with the existing Ansible ecosystem project
of that name.

## Goals

- Own menu and application flow for project-local management tools.
- Own runner and progress reporting logic for Ansible commands.
- Own prompt handling and validation.
- Provide sensible logs and state defaults.
- Expose a public API that thin wrappers can call:

```python
from ansibleRunner import main

raise SystemExit(main(arPath, argv))
```

Project wrappers should stay thin: discover the runner path, pass through CLI
arguments, and let `ansibleRunner` own the shared behavior.

## Quickstart

Run the installer from the directory that should become `arPath`:

```shell
curl -LO https://github.com/dwfa/ansibleRunner/releases/latest/download/install.py
python3 install.py
```

Start the TUI:

```shell
./ar.py
```

If your playbooks are not under the directory that contains `ar.py`, pass the
alternate playbook root:

```shell
./ar.py --pbPath /path/to/playbooks
```

## Core Paths

`ansibleRunner` separates runtime state from playbook discovery:

- `arPath`: directory containing `.venv/`, `.ansibleRunner/`, `logs/`, and the
  default `playbooks/`; also where Ansible is launched from.
- `pbPath`: directory used for playbook discovery and nested playbook helpers.
  Defaults to `arPath/playbooks`, and can be overridden with `--pbPath`.

See [Project Layout](docs/projectLayout.md) for supported layout options.

## Documentation

- [Installation](docs/installation.md): installer options, wheel installs,
  local checkout installs, and offline notes.
- [Project Layout](docs/projectLayout.md): `arPath`, `pbPath`, state, logs, and
  generated files.
- [Nested Playbooks](docs/nestedPlaybooks.md): nested directory behavior,
  `playbookPath`, and lookup plugin examples.
- [TUI Usage](docs/tuiUsage.md): menu, launch, configure, run, and CLI usage.
- [Display Wrappers](docs/displayWrappers.md): `@ar:hide`, `@ar:show`,
  `niceWait`, `niceInput`, `niceDisplay`, `niceFail`, and AR markup.
