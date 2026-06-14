# Installation

## Requirements

Python 3.11+ is required. Verify with:

=== "macOS / Linux"
    ```bash
    python3 --version   # must be 3.11 or higher
    ```

=== "Windows (PowerShell)"
    ```powershell
    python --version    # must be 3.11 or higher
    ```

!!! note "`python` vs `python3`"
    On Windows the interpreter is usually `python` (and `pip`). On macOS/Linux it
    is usually `python3` (and `pip3`). Use whichever resolves on your machine —
    the rest of this guide writes `python`/`pip` for brevity.

## Install from PyPI (recommended once available)

```bash
pip install opencomplai
```

!!! warning "Pre-release status"
    `opencomplai` is at version `0.1.0-dev` and has not yet been published to PyPI.
    If `pip install opencomplai` fails with a "not found" error, install from source (see below).

## Install from source

The packages are not yet on PyPI, so the editable install must include the
local `core` and `cli` packages **in the same command** — otherwise pip tries
(and fails) to resolve `opencomplai-core` / `opencomplai-cli` from PyPI.

=== "macOS / Linux"
    ```bash
    git clone https://github.com/Checkref-co/opencomplai
    cd opencomplai
    pip install -e packages/core -e packages/cli -e packages/sdk-python
    ```

=== "Windows (PowerShell)"
    ```powershell
    git clone https://github.com/Checkref-co/opencomplai
    cd opencomplai
    pip install -e packages/core -e packages/cli -e packages/sdk-python
    ```

This installs the core engine, the CLI (which provides the `opencomplai`
command), and the SDK in editable mode. `cryptography` is pulled in
automatically as a dependency of `opencomplai-core`.

!!! warning "Do not run `pip install -e packages/sdk-python` on its own"
    On a fresh machine that fails with
    `No matching distribution found for opencomplai-cli>=0.1.0-dev`, because the
    SDK's dependencies are local monorepo packages not published to PyPI. Always
    pass `core`, `cli`, and `sdk-python` together as shown above.

### Alternative: `uv` (workspace install)

The repository is a [uv](https://github.com/astral-sh/uv) workspace. If you have
`uv` installed, a single command installs every package in editable mode:

```bash
uv sync
```

Then prefix commands with `uv run` (e.g. `uv run opencomplai check`) or activate
the created `.venv`.

## Verify the installation

The CLI does not expose a `--version` flag. Verify with `--help` (lists the
available commands) and `pip show` (prints the installed version):

```bash
opencomplai --help
pip show opencomplai          # Version: 0.1.0.dev0
```

A successful `opencomplai --help` lists `init`, `check`, `eval`,
`validate-manifest`, `risk`, `docs`, `keys`, and more.

## Signed artifacts work out of the box

`cryptography` is a required dependency of `opencomplai-core`, so the Ed25519
signing keypair is created automatically on first `opencomplai init`, and
`opencomplai check --sign` produces a signed artifact (`signed: yes`) with no
extra install step. Compliance checks also work normally **without** `--sign`
(`signed: no (OSS unsigned)`).