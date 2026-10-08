# opencomplai-cli

[![License: AGPL-3.0](https://img.shields.io/badge/license-AGPL--3.0-blue.svg)](https://www.gnu.org/licenses/agpl-3.0)
[![PyPI](https://img.shields.io/pypi/v/opencomplai-cli.svg)](https://pypi.org/project/opencomplai-cli/)
[![Python](https://img.shields.io/badge/python-3.11%2B-blue.svg)](https://www.python.org/)

The `opencomplai` command-line tool for AI compliance assessment. It scans your
repository, classifies your AI system against the EU AI Act, reports gaps for every
framework your manifest targets (NIST AI RMF 1.0 is derived from the EU AI Act evidence),
and produces an auditable, CI-gateable compliance artifact. EU AI Act evaluated; NIST AI RMF derived (partial, unreviewed); ISO 42001 native pack, attestation-led (partial, unreviewed); DORA and EBA mapped only.

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
| `opencomplai gaps` | Print a gap report for every target framework, the EU AI Act by default (informational — never gates CI) |
| `opencomplai diff` | Compare two artifacts or gap reports: added, removed and changed verdicts and the rule-set version delta (`--fail-on-regression` exits 1 on a worse status) |
| `opencomplai recommend` | Write copy-paste remediation templates for Missing/Partial gap-report rows |
| `opencomplai report` | Render a single shareable HTML/PDF compliance report |
| `opencomplai eval` | Run safety, bias, and data-leakage pipeline evaluators |
| `opencomplai validate-manifest` | Validate a `system-manifest.json` against the required schema; deep-checks an `agent_inventory` block |
| `opencomplai serve` | Start a localhost-only scan dashboard (not Pro/SaaS) |
| `opencomplai approve` | Mint a signed HITL approval token for a `HALTED_PENDING_REVIEW` system |
| `opencomplai resume` | Resume a `HALTED_PENDING_REVIEW` system with a signed approval token |
| `opencomplai accept` | Write a signed, committable record accepting a system's high-risk classification |
| `opencomplai verify-output` | Verify an AI output claim against ground-truth sources |
| `opencomplai verify` | Verify a signed artifact (`--kind` artifact, dossier or agent-attestation; `--expect KEY=VALUE` adds offline checks) |
| `opencomplai version` | Show the installed Opencomplai version |
| `opencomplai info` | Show full package metadata (`pip show`-style, across the whole suite) |

Also available as command groups (`opencomplai <group> --help` for their own subcommands):
`docs` (Annex IV dossier generation), `instructions` (Art. 13 instructions-for-use), `deployer-pack` (seal instructions-for-use into a hash-named, offline-verifiable pack), `risk` (risk classification), `sync` (metadata sync),
`keys` (signing-key rotation), `ai` (optional AI-intent plugin configuration), `controls`
(control-register status), `fria` (fundamental rights impact assessment), `qms` (Art. 17 quality-management-system documents), `dashboard` (Premium Dashboard connection management),
`incident` (incident records and deadline clocks),
`agents` (declared agent inventory: list, cross-check against a scan, report; `agents attest` signs an agent mandate attestation)
and `rules` (rule-set history: `opencomplai rules changelog`).
Per-command pages are at <https://docs.opencomplai.com/cli/>.

`gaps`, `report` and `recommend` accept `--sort priority` to list rows by regulatory deadline, then
severity (Missing first), then fix effort (S, M, L); the default is `--sort article`. Met rows come last,
rows without a known deadline or effort sort after dated ones, and effort is a rough engineering
estimate. `gaps -o json` adds a top-level `backlog` block under `--sort priority`; the `articles` list
keeps article order.

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

`check` can also write CI reports from the same verdict, without changing the exit code:
`--report-junit PATH` (JUnit XML), `--sarif-output PATH` (SARIF 2.1.0 of the verdict, not scan
evidence) and `--summary-md PATH` (Markdown job summary).

To publish an Annex IV dossier instead of (or in addition to) a scan-status artifact, run
`opencomplai docs generate --system-id ... --push` — same `OPENCOMPLAI_API_KEY` /
`OPENCOMPLAI_DASHBOARD_URL` as `opencomplai push` above.

## Optional: AI intent analysis

Install the [`opencomplai-ai`](https://pypi.org/project/opencomplai-ai/) plugin to unlock
the `--ai-intent` flag, which classifies how each AI callsite is actually used:

```bash
pip install opencomplai-ai
opencomplai scan --ai-intent --ai-model codebert-onnx   # deterministic matcher, no download
```

The default model is a local GGUF LLM and needs `pip install 'opencomplai-ai[deep]'`;
without it a bare `--ai-intent` prints `AI intent skipped`.

## Documentation

Full CLI reference and guides at **[docs.opencomplai.com](https://docs.opencomplai.com)**.

## License

AGPL-3.0-only. See [LICENSE](https://www.gnu.org/licenses/agpl-3.0).
