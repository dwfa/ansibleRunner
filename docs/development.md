<!--
##############################################################################
# Development
#
# Local checkout, build, and test notes for ansibleRunner maintainers.
#
# Copyright 2026 Douglas WF Acheson (dwfa@dwfa.ca)
# Licensed under Apache License 2.0. See LICENSE.md for details.
#
# Version: 1.0
# Date: August 21, 2026
##############################################################################
-->

# Development

This page is for maintaining `ansibleRunner` itself. For normal toolkit
installation, see [Installation](installation.md).

## Local Install

Install from a local checkout:

```shell
python3 -m pip install .
```

Install editable development dependencies:

```shell
python3 -m pip install -e ".[dev]"
```

## Build

Build a wheel:

```shell
scripts/build.py
```

Build artifacts are written under `dist/`. Detailed build logs are written
under `logs/`.

## Test

Run the full test suite:

```shell
scripts/test.py all
```

Run a focused scope:

```shell
scripts/test.py unit
scripts/test.py blackBox
scripts/test.py tests/blackBox/testCliArPath.py
```
