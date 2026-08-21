<!--
##############################################################################
# Nested Playbooks
#
# Nested playbook directory behavior and path helper examples for ansibleRunner.
#
# Copyright 2026 Douglas WF Acheson (dwfa@dwfa.ca)
# Licensed under Apache License 2.0. See LICENSE.md for details.
#
# Version: 1.0
# Date: August 21, 2026
##############################################################################
-->

# Nested Playbooks

Directories under `playbooks/` are supported for organizing related playbooks:

```text
playbooks/
  db/
    listServers-pb.yaml
    provisionServer-pb.yaml
  users/
    listUsers-pb.yaml
```

The playbook menu shows playbook grouping directories before playbooks. Press
`Enter` on a directory to open it, and use the `..` row to return to the parent
directory. A directory is shown only when it contains at least one runnable
playbook somewhere under it. YAML variable files and support directories such
as `playbooks/vars/` are ignored.

## Shared Path Strategy

Nested playbooks change the meaning of relative paths, because each selected
playbook can live at a different directory depth.

For shared paths, prefer resolving from a stable project anchor instead of from
the selected playbook's location. The example lookup plugins below resolve from
`inventory_dir`, so the same variables work for direct and nested playbooks.

## Lookup Plugin Examples

For projects that keep inventory under `data/` and want path resolution to work
from nested playbook directories, `docs/examples/plugins/lookup/` includes two
project-side lookup plugin examples:

- [`findDirUp.py`](examples/plugins/lookup/findDirUp.py): walks upward from
  `inventory_dir` to find shared directories such as `playbooks`, `tasks`, and
  `data`.
- [`getPyLauncherPath.py`](examples/plugins/lookup/getPyLauncherPath.py):
  returns the Python interpreter running `ansible-playbook`, useful for
  inventories that should use the launcher venv.

Copy those examples into a project-local `plugins/lookup/` directory, then use
the path lookup in `data/group_vars/all.yaml`:

```yaml
pbPath:   "{{ lookup('findDirUp', 'playbooks', inventory_dir) }}"
taskPath: "{{ lookup('findDirUp', 'tasks',     inventory_dir) }}"
dataPath: "{{ lookup('findDirUp', 'data',      inventory_dir) }}"
```

Then includes and vars files can stay stable whether the playbook is a direct
child of `playbooks/` or inside a grouping directory:

```yaml
- name: Load shared path variables
  ansible.builtin.include_vars:
    file: "{{ pbPath }}/vars/paths.yaml"

- name: Confirm action
  ansible.builtin.include_tasks: "{{ taskPath }}/misc/niceWait.yaml"
  vars:
    title: "Confirm action"
    data: "Press Enter to continue."
```

Inventory entries that need the launcher's Python can use:

```yaml
ansible_python_interpreter: "{{ lookup('getPyLauncherPath') }}"
```

For example, a project-local inventory can point local/controller execution at
the same virtual environment that launched `ansible-playbook`:

```yaml
all:
  children:
    local:
      hosts:
        localhost:
          ansible_connection: local
          ansible_python_interpreter: "{{ lookup('getPyLauncherPath') }}"
```

Keep this scoped to local/controller hosts. Do not set it globally for remote
hosts unless those hosts really have the same Python path.

## playbookPath Compatibility

AR also passes `playbookPath` on every run. It is a relative path from the
selected playbook's directory back to `pbPath`.

Keep `playbookPath` as a compatibility helper for existing project layouts or
for playbooks that explicitly want AR's relative path value. New projects
should prefer the lookup plugin pattern above for shared paths, because those
variables are owned by the project and do not depend on where a playbook lives.

```text
playbooks/site-pb.yaml       -> playbookPath=./
playbooks/db/list-pb.yaml    -> playbookPath=../
playbooks/db/ops/run-pb.yaml -> playbookPath=../../
```

AR does not prescribe how `playbookPath` is combined with project-specific
variables. That choice belongs in the project using the playbooks.

For example, a project that wants to use AR's relative path helper directly
could define project variables like this:

```yaml
pbPath:   "{{ playbookPath }}"
taskPath: "{{ playbookPath }}../tasks"
```

When running without AR, pass the same value manually if the playbook relies on
`playbookPath`:

```shell
ansible-playbook --extra-vars "playbookPath=../" playbooks/db/list-pb.yaml
```
