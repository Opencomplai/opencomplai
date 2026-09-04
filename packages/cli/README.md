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
| `opencomplai push` | Publish a signed artifact (scan status or Annex IV dossier) to the Premium Dashboard |
| `opencomplai checker` | Run the interactive EU AI Act applicability checker |
| `opencomplai gaps` | Print a per-article EU AI Act gap report (informational — never gates CI) |
| `opencomplai recommend` | Write copy-paste remediation templates for Missing/Partial gap-report rows |
| `opencomplai report` | Render a single shareable HTML/PDF compliance report |
| `opencomplai eval` | Run safety, bias, and data-leakage pipeline evaluators |
| `opencomplai validate-manifest` | Validate a `system-manifest.json` against the required schema |
| `opencomplai serve` | Start a localhost-only scan dashboard (not Pro/SaaS) |
| `opencomplai approve` | Mint a signed HITL approval token for a `HALTED_PENDING_REVIEW` system |
| `opencomplai resume` | Resume a `HALTED_PENDING_REVIEW` system with a signed approval token |
| `opencomplai verify-output` | Verify an AI output claim against ground-truth sources |
| `opencomplai version` | Show the installed Opencomplai version |
| `opencomplai info` | Show full package metadata (`pip show`-style, across the whole suite) |

Also available as command groups (`opencomplai <group> --help` for their own subcommands):
`docs` (Annex IV dossier generation), `risk` (risk classification), `sync` (metadata sync),
`keys` (signing-key rotation), `ai` (optional AI-intent plugin configuration), `controls`
(control-register status).

Run `opencomplai --help` for the full command list, or `opencomplai <command> --help` for
options.

## Quick start

The self-serve path: mint a key on the dashboard, export two env vars, sign a scan, push it.

```bash
# 1. Scaffold a manifest for your project
opencomplai init

# 2. Cross-check the manifest against your source tree
opencomplai scan --manifest system-manifest.json --repo-root .

# 3. Get an API key from the dashboard's /connect page (Projects -> your
#    project -> Connect), then export it alongside the dashboard's ingest URL
export OPENCOMPLAI_API_KEY=ock_...
export OPENCOMPLAI_DASHBOARD_URL=https://your-dashboard-host/api/ingest

# 4. Run the compliance gate and sign the artifact (writes compliance-artifact.json)
opencomplai check --sign

# 5. Push the signed artifact to the dashboard
opencomplai push
```

Following this start-to-finish lands the scan on the dashboard's `/systems` page for that
project. `/connect` also generates ready-to-paste GitHub Actions / GitLab CI snippets that
wire the same two env vars into a pipeline — see
[CI integration](https://docs.opencomplai.com/guides/ci-integration/).

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

To publish an Annex IV dossier instead of (or in addition to) a scan-status artifact, run
`opencomplai docs generate --system-id ... --push` — same `OPENCOMPLAI_API_KEY` /
`OPENCOMPLAI_DASHBOARD_URL` as `opencomplai push` above.

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
