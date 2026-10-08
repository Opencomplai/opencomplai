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

### Install as a tool (uv or pipx)

To get the `opencomplai` command in its own isolated environment, use `uv tool` or
`pipx`. Either puts `opencomplai` on your PATH.

=== "macOS / Linux"
    ```bash
    uv tool install opencomplai
    # or
    pipx install opencomplai
    ```

=== "Windows (PowerShell)"
    ```powershell
    uv tool install opencomplai
    # or
    pipx install opencomplai
    ```

### One-line install (uv-managed Python)

If you have no Python installed, or want one that does not touch your system
Python, the install script wraps `uv tool install` and asks `uv` for its own
Python (3.11, the minimum Opencomplai supports). Download the script, then run it:

=== "macOS / Linux"
    ```bash
    curl -fsSLO https://raw.githubusercontent.com/Opencomplai/opencomplai/main/scripts/install.sh
    bash install.sh
    ```

=== "Windows (PowerShell)"
    ```powershell
    Invoke-WebRequest https://raw.githubusercontent.com/Opencomplai/opencomplai/main/scripts/install.ps1 -OutFile install.ps1
    ./install.ps1
    ```

- It needs network access and installs only the PyPI packages.
- If `uv` is missing the script prints how to install it and exits with code 1.
  Pass `--install-uv` (`-InstallUv` on Windows) to let it run the official uv
  installer for you.
- `--python <version>` (`-Python`) or the `OPENCOMPLAI_PYTHON` environment
  variable picks another interpreter; the default is `3.11`, the minimum.
- The script does not edit your shell profile or PATH. If the tool directory is
  not on your PATH it prints the directory to add.

The contributor wheel smoke check (`scripts/smoke_wheel_install.sh`) is unchanged.

### Homebrew (planned)

On macOS and Linux, once the tap is published:

```bash
brew tap Opencomplai/tap
brew install opencomplai
```

or in one step: `brew install Opencomplai/tap/opencomplai`.

The tap is not yet published. The formula file lives at
`packaging/homebrew/opencomplai.rb` in the repository, with the tap steps in
`packaging/homebrew/README.md`. Windows users use the PowerShell script above, or
`pip` or `uv`.

### Published packages

| Package | PyPI | Install | Use when |
|---------|------|---------|----------|
| `opencomplai` | [opencomplai](https://pypi.org/project/opencomplai/) | `pip install opencomplai` | Default — meta-package (core + CLI + SDK) |
| `opencomplai-core` | [opencomplai-core](https://pypi.org/project/opencomplai-core/) | `pip install opencomplai-core` | Embedding the risk engine in your own app |
| `opencomplai-cli` | [opencomplai-cli](https://pypi.org/project/opencomplai-cli/) | `pip install opencomplai-cli` | CLI only (pulls in core) |
| `opencomplai-ai` | [opencomplai-ai](https://pypi.org/project/opencomplai-ai/) | `pip install opencomplai-ai` | Optional `--ai-intent` scan plugin |

For the current version, see the [release history on
PyPI](https://pypi.org/project/opencomplai/#history).

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

Verify with `--help` (lists the available commands) and `--version` (prints
the installed version):

=== "macOS / Linux"
    ```bash
    opencomplai --help
    opencomplai --version
    ```

=== "Windows (PowerShell)"
    ```powershell
    opencomplai --help
    opencomplai --version
    ```

`opencomplai version` prints the same string, and `pip show opencomplai`
still works if you want the full distribution metadata.

A successful `opencomplai --help` lists `init`, `check`, `eval`,
`validate-manifest`, `risk`, `docs`, `keys`, and more.

## Signed artifacts work out of the box

`cryptography` is a required dependency of `opencomplai-core`, so the Ed25519
signing keypair is created automatically on first `opencomplai init`, and
`opencomplai check --sign` produces a signed artifact (`signed: yes`) with no
extra install step. Compliance checks also work normally **without** `--sign`
(`signed: no (OSS unsigned)`).