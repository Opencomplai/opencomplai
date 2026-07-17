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

## Install from PyPI (recommended)

=== "macOS / Linux"
    ```bash
    pip install opencomplai
    ```

=== "Windows (PowerShell)"
    ```powershell
    pip install opencomplai
    ```

### Published packages

| Package | PyPI | Install | Use when |
|---------|------|---------|----------|
| `opencomplai` | [opencomplai](https://pypi.org/project/opencomplai/) | `pip install opencomplai` | Default — meta-package (core + CLI + SDK) |
| `opencomplai-core` | [opencomplai-core](https://pypi.org/project/opencomplai-core/) | `pip install opencomplai-core` | Embedding the risk engine in your own app |
| `opencomplai-cli` | [opencomplai-cli](https://pypi.org/project/opencomplai-cli/) | `pip install opencomplai-cli` | CLI only (pulls in core) |
| `opencomplai-ai` | [opencomplai-ai](https://pypi.org/project/opencomplai-ai/) | `pip install opencomplai-ai` | Optional `--ai-intent` scan plugin |

Latest release: **0.1.2** on PyPI.

## Optional extras

| Extra | Install | What you get |
|-------|---------|--------------|
| *(default)* | `pip install opencomplai` | check, scan, gaps, recommend, lexical evaluators — air-gap safe |
| `reports` | `pip install 'opencomplai[reports]'` | PDF via fpdf2 |
| `inspect-bridge` | `pip install 'opencomplai[inspect-bridge]'` | Inspect-AI curated suite (never used by `check`) |
| `serve` | `pip install 'opencomplai[serve]'` | Localhost dashboard (`opencomplai serve`) |

**Don't** install the bridge or serve extras into production gate images unless you
intentionally want those network surfaces. `opencomplai check` never pulls Inspect.


## Install from source

For contributors or bleeding-edge development, install from the repository. The local
`core` and `cli` packages must be installed in the **same command** as the SDK —
otherwise pip tries (and fails) to resolve `opencomplai-core` / `opencomplai-cli` from PyPI.

=== "macOS / Linux"
    ```bash
    git clone https://github.com/Opencomplai/opencomplai
    cd opencomplai
    pip install -e packages/core -e packages/cli -e packages/sdk-python
    ```

=== "Windows (PowerShell)"
    ```powershell
    git clone https://github.com/Opencomplai/opencomplai
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

=== "macOS / Linux"
    ```bash
    uv sync
    ```

=== "Windows (PowerShell)"
    ```powershell
    uv sync
    ```

Then prefix commands with `uv run` (e.g. `uv run opencomplai check`) or activate
the created `.venv`.

## Verify the installation

The CLI does not expose a `--version` flag. Verify with `--help` (lists the
available commands) and `pip show` (prints the installed version):

=== "macOS / Linux"
    ```bash
    opencomplai --help
    pip show opencomplai          # Version: 0.1.2
    ```

=== "Windows (PowerShell)"
    ```powershell
    opencomplai --help
    pip show opencomplai          # Version: 0.1.2
    ```

A successful `opencomplai --help` lists `init`, `check`, `eval`,
`validate-manifest`, `risk`, `docs`, `keys`, and more.

## Signed artifacts work out of the box

`cryptography` is a required dependency of `opencomplai-core`, so the Ed25519
signing keypair is created automatically on first `opencomplai init`, and
`opencomplai check --sign` produces a signed artifact (`signed: yes`) with no
extra install step. Compliance checks also work normally **without** `--sign`
(`signed: no (OSS unsigned)`).