<!--
##############################################################################
# Project Layout
#
# Runtime path and generated file layout for ansibleRunner projects.
#
# Copyright 2026 Douglas WF Acheson (dwfa@dwfa.ca)
# Licensed under Apache License 2.0. See LICENSE.md for details.
#
# Version: 1.0
# Date: August 21, 2026
##############################################################################
-->

# Project Layout

`ansibleRunner` separates the runtime anchor from the playbook root:

- `arPath`: directory containing `.venv/`, `.ansibleRunner/`, `logs/`, and the
  default `playbooks/`; also where Ansible is launched from.
- `pbPath`: directory used for playbook discovery and nested playbook helpers.
  Defaults to `arPath/playbooks`, and can be overridden with `--pbPath`.

## Supported Structures

`arPath` can be the project directory itself, or it can be a subdirectory inside
a larger project. Both layouts are supported equally.

### arPath as projectPath

```text
projectPath/
├── ar.py                         # Thin launcher written by the installer
├── .venv/                        # Project-local Python and ansible-playbook
├── .ansibleRunner/
│   └── state/
│       └── playbookConfig.json
├── logs/
│   ├── ansibleRunner-install-<timestamp>.log
│   ├── <playbook>-<timestamp>.log
│   └── <playbook>-<timestamp>.events.jsonl
├── playbooks/                    # Default pbPath and TUI menu root
│   ├── site-pb.yaml
│   ├── vars/                     # Support files; not shown as playbooks
│   │   └── connectionKey.yaml
│   └── db/                       # Grouping directory shown in the TUI
│       ├── listServers-pb.yaml
│       └── provisionServer-pb.yaml
├── data/                         # Optional Ansible-owned inventory/vars
├── plugins/                      # Optional Ansible plugins
├── tasks/                        # Optional shared include_tasks files
└── roles/                        # Optional Ansible roles
```

### arPath as a Subdirectory

```text
projectPath/
├── app-or-repo-files/            # Your project-owned files
└── ansiblePath/                  # arPath
    ├── ar.py                     # Thin launcher written by the installer
    ├── .venv/                    # Project-local Python and ansible-playbook
    ├── .ansibleRunner/
    │   └── state/
    │       └── playbookConfig.json
    ├── logs/
    │   ├── ansibleRunner-install-<timestamp>.log
    │   ├── <playbook>-<timestamp>.log
    │   └── <playbook>-<timestamp>.events.jsonl
    ├── playbooks/                # Default pbPath and TUI menu root
    │   ├── site-pb.yaml
    │   ├── vars/                 # Support files; not shown as playbooks
    │   │   └── connectionKey.yaml
    │   └── db/                   # Grouping directory shown in the TUI
    │       ├── listServers-pb.yaml
    │       └── provisionServer-pb.yaml
    ├── data/                     # Optional Ansible-owned inventory/vars
    ├── plugins/                  # Optional Ansible plugins
    ├── tasks/                    # Optional shared include_tasks files
    └── roles/                    # Optional Ansible roles
```

## Expected Files

- `pbPath`: playbook menu root. Direct child directories that contain runnable
  playbooks are shown first for grouping, followed by direct child `*.yaml` and
  `*.yml` playbooks. Press `Enter` on a directory to open it.
- The first meaningful `# ...` comment near the top of a playbook is shown as
  the playbook title. If no title exists, the TUI shows `(no title)`.
- A saved `Node` value or launch-time `-n <node>` value is optional. When set,
  the runner passes that target through to Ansible as `nodes=<value>`. When
  unset, the playbook is run without a `nodes` extra-var and can use its own
  `hosts`, inventory, or variables.
- Every run receives `playbookPath` as an extra-var for playbooks that include
  files relative to `pbPath`. Direct child playbooks get `playbookPath=./`; a
  playbook one directory down gets `playbookPath=../`.
- `ansible-core` is installed into `.venv`, so `ar.py` uses the project-local
  `ansible-playbook` command. Project-specific collections, roles, inventory,
  and Ansible configuration remain owned by the Ansible project.

## Generated Files

Files created by the installer:

- `.venv/`: project-local Python virtual environment.
- `ar.py`: project-local launcher. This file knows `arPath`, so normal project
  usage does not require `--arPath`. Any other arguments, including
  `--pbPath`, are passed through to the installed `ansibleRunner` command.
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
