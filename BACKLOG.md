<!--
##############################################################################
# BACKLOG.md
#
# Prioritized future work for ansibleRunner.
#
# Copyright 2026 Douglas WF Acheson (dwfa@dwfa.ca)
# Licensed under Apache License 2.0. See LICENSE.md for details.
#
# Version: 1.0
# Date: July 23, 2026
##############################################################################
-->

# Backlog

## P1

- Support masked prompt input through an explicit prompt variable.
  Text prompt input is visible by default to match `promptForInput` tasks that
  use `echo: true`. Add a documented variable convention, such as
  `promptHidden: true`, so playbooks can request password-style masking for
  sensitive interactive values without making ordinary prompts harder to use.

- Audit and clarify run pipeline separation of concerns.
  Review `RunScreen`, callback/stdout processing, prompt/display wrapper
  interception, progress mutation, input handling, and rendering boundaries.
  Identify where responsibilities are mixed, then split the highest-risk areas
  into explicit components so detection/interception, execution, state updates,
  and Textual rendering can be tested independently.

## P2

- Support orchestrator playbooks with phase-specific target variables.
  Single-playbook runs currently pass one `nodes=<value>` extra-var. For
  imported/orchestrator playbooks, document and optionally support a convention
  where each phase can target a different inventory group through variables such
  as `buildRPiImageNode`, `postCreateNode`, or `buildDNSServerNode`, with
  `nodes` retained as the single-playbook fallback.

- Consider allowing playbooks to run without a configured node.
  Current behavior requires a saved `Node` value or `-n <node>` so the runner
  can pass `nodes=<value>` consistently. Some playbooks may intentionally
  define their own hosts and need no runner-supplied target. Decide whether to
  support an explicit opt-out setting before changing the default guard.
