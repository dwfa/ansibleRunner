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

## P2

- Support orchestrator playbooks with phase-specific target variables.
  Single-playbook runs currently pass one `nodes=<value>` extra-var. For
  imported/orchestrator playbooks, document and optionally support a convention
  where each phase can target a different inventory group through variables such
  as `buildRPiImageNode`, `postCreateNode`, or `buildDNSServerNode`, with
  `nodes` retained as the single-playbook fallback.
