<!--
##############################################################################
# Display Wrappers
#
# AR display hints, prompt wrappers, display wrappers, and markup notes.
#
# Copyright 2026 Douglas WF Acheson (dwfa@dwfa.ca)
# Licensed under Apache License 2.0. See LICENSE.md for details.
#
# Version: 1.0
# Date: August 21, 2026
##############################################################################
-->

# Display Wrappers

`ansibleRunner` supports AR display hints, such as `@ar:hide` and `@ar:show`,
plus four small Ansible wrapper task files. The wrappers are split into two
prompt wrappers, `niceWait` and `niceInput`, and two display wrappers,
`niceDisplay` and `niceFail`. Together they let AR render cleaner TUI prompts,
display blocks, and failure messages. The wrappers are optional. A playbook can
still run with normal `ansible-playbook`; the wrapper task names give AR a
stable title to read from Ansible output and callback events.

Detection is based on the included wrapper filename, so the files may live
wherever a project keeps shared tasks.

## AR Display Hints

Task, role, and play names may include AR display hints. Use `@ar:hide` when a
row should be omitted from the AR progress tree, and use `@ar:show` when a row
should remain visible even when the selected `--outputLevel` would normally
collapse it.

```yaml
- name: "load temporary vars @ar:hide"
  ansible.builtin.include_vars:
    file: temp.yaml
```

Display rules:

- AR strips `@ar:hide` from matching and display names.
- AR strips `@ar:show` from matching and display names.
- A hidden task suppresses that task row. For `niceDisplay`, this is how the
  wrapper task becomes only the boxed output block.
- `@ar:show` forces a row to render even when the selected `--outputLevel`
  would normally collapse it.
- `@ar:hide` and `@ar:show` cannot be combined on the same name; AR treats that
  as invalid playbook metadata.
- A hidden role suppresses the role row when Ansible's emitted role segment
  contains `@ar:hide`; visible child tasks can still render.
- A hidden play suppresses the play row; visible child roles/tasks can still
  render.
- Completed `niceWait` and `niceInput` prompt history rows are AR interaction
  records, not Ansible task rows.
- Plain `ansible-playbook` still shows the literal task name, including the
  hint.

## Prompt Wrappers

Use `niceWait.yaml` for continue prompts and `niceInput.yaml` for text input
prompts. In the playbook, include the wrapper file and pass:

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
- `niceWait.yaml` is treated as a continue prompt; `niceInput.yaml` is treated
  as a text prompt.
- Native Ansible prompt text from the run log wins when present.
- Multiline prompt text is preserved in the input panel.
- Internal `nice*` wrapper task rows are hidden from the progress tree.
- Completed prompt interactions remain visible in normal role/task progress.

## Display Wrappers

Use `niceDisplay.yaml` for boxed informational output and `niceFail.yaml` for
boxed failure output that stops the playbook. Both display wrappers accept:

- `title`: short box title shown by AR.
- `data`: display payload printed by Ansible and rendered by AR. A string,
  multiline block, list, or mapping can be used.

## AR Markup

`title` and `data` values for `niceWait`, `niceInput`, `niceDisplay`, and
`niceFail` may use AR-only style tags. The tags are rendered by the TUI and
stripped from copy/prompt summaries. Plain `ansible-playbook` output still
shows the tags as ordinary text.

Supported tags:

```text
{bold}...{/bold}
{dim}...{/dim}
{red}...{/red}
{green}...{/green}
{yellow}...{/yellow}
{blue}...{/blue}
{magenta}...{/magenta}
{cyan}...{/cyan}
{white}...{/white}
```

Example:

```yaml
vars:
  title: "{green}Provision complete{/green}"
  data: |
    server = {cyan}example-db-01{/cyan}
    status = {green}deleted{/green}
```

AR uses `{style}` tags instead of Rich-style `[style]` tags so normal Ansible
values like `[example-db-01]` and `[/tmp/currentRPiImage.img]` remain safe.

## niceDisplay

Use `niceDisplay.yaml` when a task should render a boxed display block instead
of a normal task row.

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
- The include row and internal `niceDisplay` task row are hidden.
- Only the boxed title and payload are shown.
- `niceDisplay:` is stripped from the boxed title.
- At `--outputLevel role`, ordinary task rows remain hidden.
- If the same role has completed prompt interactions, those prompt rows are not
  appended below the boxed display block.
- Press `y` to copy the full boxed output block.

## niceFail

Use `niceFail.yaml` when a task should stop the playbook with a clean boxed
failure message.

Playbook usage:

```yaml
- name: "Validate required settings"
  ansible.builtin.include_tasks: "path/to/niceFail.yaml"
  vars:
    title: "Missing required settings"
    data:
      - "server = [unset]"
      - "env    = [dev]"
```

Display rules:

- The reusable wrapper task uses `niceFail:` in its own task name so AR can
  read the title from Ansible output.
- The include row and internal `niceFail` task row are hidden.
- The boxed title and payload are shown before the failed run summary.
- `niceFail:` is stripped from the boxed title.
- Normal Ansible failure semantics are preserved; the playbook fails under AR
  and under plain `ansible-playbook`.

## Wrapper Task Files

Projects can copy and adapt these reusable task files wherever shared task
files live.

`niceWait.yaml`:

```yaml
---
- name: "niceWait: {{ title | default('Wait for user input') }}"
  ansible.builtin.pause:
    prompt: "{{ data | default('Press Enter to continue.') }}"
    echo: false
```

`niceInput.yaml`:

```yaml
---
- name: "niceInput: {{ title | default('Prompt user for input.') }}"
  ansible.builtin.pause:
    prompt: "{{ data | default('Enter value ...') }}"
    echo: true
  register: promptInput

- name: "set prompted value"
  ansible.builtin.set_fact:
    promptValue: "{{ promptInput.user_input | default('') | trim }}"
```

`niceDisplay.yaml`:

```yaml
---
- name: "niceDisplay: {{ title | default('Default Title') }}"
  ansible.builtin.debug:
    msg: "{{ data }}"
```

`niceFail.yaml`:

```yaml
---
- name: "niceFail: {{ title | default('Failure') }}"
  ansible.builtin.fail:
    msg: "{{ data }}"
```
