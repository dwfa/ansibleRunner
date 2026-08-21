<!--
##############################################################################
# TUI Usage
#
# Textual menu, launch, configure, run, and CLI usage for ansibleRunner.
#
# Copyright 2026 Douglas WF Acheson (dwfa@dwfa.ca)
# Licensed under Apache License 2.0. See LICENSE.md for details.
#
# Version: 1.0
# Date: August 21, 2026
##############################################################################
-->

# TUI Usage

Start the project launcher:

```shell
./ar.py
```

The first screen lists directories and playbooks from `pbPath`.

## Playbook Menu

- Use `Up` and `Down` to move.
- Press `Enter` on a directory to open it.
- Select `..` to return to the parent directory when browsing nested
  playbooks.
- Press `Enter` on a playbook to review and run it.
- Press `c` to edit saved settings for the selected playbook.
- Press `q` or `Esc` to quit.

## Launch Screen

The launch screen shows the exact Ansible arguments that will be used.

- Press `Enter` or `r` to run.
- Press `e` to edit settings for this run only.
- Press `c` to edit and save settings for future runs.
- Press `q` or `Esc` to return to the playbook list.

## Configure Screen

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

Run option behavior:

- `-n <node>` is optional. AR only adds `nodes=<value>` when a node is set.
- `-d` adds `debugFlag=1`.
- `-c`, `-s`, and `-t` become `--check`, `--syntax-check`, and
  `--list-tasks`.
- `--outputLevel` changes only the AR progress view; it is not passed to
  `ansible-playbook`.
- Extra Ansible arguments are passed through after AR's managed `--extra-vars`
  and before the playbook path. Use this for options such as `--tags`,
  `--skip-tags`, `--limit`, `--inventory`, or additional `--extra-vars`.
- AR always adds `playbookPath=<value>` so nested playbooks can resolve shared
  project paths as described in [Nested Playbooks](nestedPlaybooks.md).

Use `Left` and `Right` to change choice/boolean fields, `Enter` to edit text
fields, `s` to save or apply, and `q`/`Esc` to go back.

## Run Screen

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
  use terminal-native text selection when supported.

## Direct CLI

When using the project launcher, do not pass `--arPath`; the launcher sets it
for you.

Use `--arPath` only when invoking the installed package directly, outside a
project launcher:

```shell
ansibleRunner --arPath /path/to/ansiblePath
```

Use `--pbPath` with the installed package when playbooks live somewhere other
than `arPath/playbooks`:

```shell
ansibleRunner --arPath /path/to/ansiblePath --pbPath /path/to/playbooks
```

With the project launcher, omit `--arPath` and pass only the alternate
playbook root:

```shell
./ar.py --pbPath /path/to/playbooks
```

With no diagnostic flag, `ansibleRunner` opens the Textual playbook menu for
the selected playbook root.

To print resolved defaults without opening the TUI:

```shell
ansibleRunner --arPath /path/to/ansiblePath --listDefaults
```

For local development:

```shell
python3 -m ansibleRunner --arPath /path/to/ansiblePath --listDefaults
```
