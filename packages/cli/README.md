# opencomplai-cli

[![License: AGPL-3.0](https://img.shields.io/badge/license-AGPL--3.0-blue.svg)](https://www.gnu.org/licenses/agpl-3.0)
[![PyPI](https://img.shields.io/pypi/v/opencomplai-cli.svg)](https://pypi.org/project/opencomplai-cli/)
[![Python](https://img.shields.io/badge/python-3.11%2B-blue.svg)](https://www.python.org/)

The `opencomplai` command-line tool for EU AI Act compliance assessment. It scans your
repository, classifies your AI system against the EU AI Act, and produces an auditable,
CI-gateable compliance artifact.

Built on [`opencomplai-core`](https://pypi.org/project/opencomplai-core/) — the same
deterministic, rule-based risk engine, with a rich terminal UX.

## Install

```bash
pip install opencomplai-cli
```

This pulls in `opencomplai-core[reports]` automatically. To install the full suite
(engine + CLI) in one step, use the [`opencomplai`](https://pypi.org/project/opencomplai/)
meta-package instead.

## Core commands

| Command | What it does |
|---|---|
| `opencomplai init` | Scaffold a `system-manifest.json` for your project |
| `opencomplai scan` | Corroborate the manifest against your code and report discrepancies |
| `opencomplai check` | Run the compliance gate and write `compliance-artifact.json` |
| `opencomplai dashboard` | Manage premium dashboard enrollment and sync |

Run `opencomplai --help` for the full command list, or `opencomplai <command> --help` for
options.

## Quick start

```bash
# 1. Scaffold a manifest for your project
opencomplai init

# 2. Cross-check the manifest against your source tree
opencomplai scan --manifest system-manifest.json --repo-root .

# 3. Run the compliance gate (writes compliance-artifact.json)
opencomplai check
```

`opencomplai check` is the canonical CI gate. Its exit code is contractual:

| Exit code | Meaning |
|---|---|
| `0` | PASS |
| `1` | CONTROL_FAIL |
| `2` | VALIDATION_FAIL |
| `3` | POLICY_BLOCK |
| `4` | TRAP_DETECTED |

So you can wire it straight into CI:

```bash
opencomplai check || exit $?
```

## Optional: AI intent analysis

Install the [`opencomplai-ai`](https://pypi.org/project/opencomplai-ai/) plugin to unlock
the `--ai-intent` flag, which classifies how each AI callsite is actually used:

```bash
pip install opencomplai-ai
opencomplai scan --ai-intent
```

## Documentation

Full CLI reference and guides at **[docs.opencomplai.com](https://docs.opencomplai.com)**.

## License

AGPL-3.0-only. See [LICENSE](https://www.gnu.org/licenses/agpl-3.0).
