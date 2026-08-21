<!--
##############################################################################
# Installation
#
# Installer, wheel, and local checkout installation notes for ansibleRunner.
#
# Copyright 2026 Douglas WF Acheson (dwfa@dwfa.ca)
# Licensed under Apache License 2.0. See LICENSE.md for details.
#
# Version: 1.0
# Date: August 21, 2026
##############################################################################
-->

# Installation

For a project-local install, download the Python installer from GitHub, inspect
it if desired, then run it from the directory that should become `arPath`:

```shell
curl -LO https://github.com/dwfa/ansibleRunner/releases/latest/download/install.py
python3 install.py
```

The installer creates `.venv`, installs `ansibleRunner`, installs runtime
dependencies including `ansible-core`, and writes `ar.py` as a thin project
launcher. During the install step it reports the package version it resolved
from the selected wheel or release asset.

## Package Source

- `python3 install.py -w ./ansiblerunner-<version>-py3-none-any.whl` installs
  the explicit wheel you provide.
- If no `-w` value is provided, the installer looks beside `install.py` for
  `ansiblerunner-*-py3-none-any.whl` and uses the newest version found there.
- If no local wheel is found, the installer downloads the newest release wheel
  from GitHub release assets.

Convenience forms:

```shell
curl -fsSL https://github.com/dwfa/ansibleRunner/releases/latest/download/install.py | python3 -
```

```shell
python3 <(curl -fsSL https://github.com/dwfa/ansibleRunner/releases/latest/download/install.py)
```

## Offline Install

If GitHub release downloads are blocked on the target machine, download both
release files on a machine that has access, copy them to `arPath`, then run the
installer there. The wheel asset is named like
`ansiblerunner-<version>-py3-none-any.whl` on the
[latest release](https://github.com/dwfa/ansibleRunner/releases/latest).

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

## Reinstall

Point the installer at a specific local wheel:

```shell
python3 install.py -w ./ansiblerunner-<version>-py3-none-any.whl
```

Force reinstall the same version when you rebuilt or re-downloaded a wheel with
the same package version:

```shell
python3 install.py --forceReinstall
```

You can combine it with an explicit wheel:

```shell
python3 install.py -w ./ansiblerunner-<version>-py3-none-any.whl --forceReinstall
```

`-w` and `--whl` are shorthand for `--packageSpec`. Use `--packageSpec`
directly when you want to pass a full custom pip package spec, such as a fork,
checkout, or test artifact.

## Direct Pip

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
