<!--
##############################################################################
# Documentation
#
# Local documentation notes and read-only shared specification guidance.
#
# Copyright 2026 Douglas WF Acheson (dwfa@dwfa.ca)
# Licensed under Apache License 2.0. See LICENSE.md for details.
#
# Version: 1.0
# Date: July 05, 2026
##############################################################################
-->

# Documentation

This directory contains the long-form documentation split out from the root
README.

## ansibleRunner Guides

- [Installation](installation.md): installer options, wheel installs, local
  checkout installs, and offline notes.
- [Project Layout](projectLayout.md): `arPath`, `pbPath`, state, logs, and
  generated files.
- [Nested Playbooks](nestedPlaybooks.md): nested directory behavior,
  `playbookPath`, and lookup plugin examples.
- [TUI Usage](tuiUsage.md): menu, launch, configure, run, and CLI usage.
- [Display Wrappers](displayWrappers.md): `@ar:hide`, `niceWait`,
  `niceInput`, `niceDisplay`, and AR markup.
- [Development](development.md): local checkout, build, and test notes for
  maintainers.

## Shared Specifications

`docs/seSpecs` is a reference-only Git submodule for this project.

Do not edit `seSpecs` content from this repository. Make changes in the
upstream `dwfa/seSpecs` repository, then update this submodule pointer when
`ansibleRunner` is ready to consume a newer revision.
