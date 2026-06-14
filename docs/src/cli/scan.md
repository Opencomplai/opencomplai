# `opencomplai scan`

Cross-check your declared `intended_purpose` against AI capability signals detected in the repository.

## Important

- **Declaration is authoritative.** The scanner corroborates your manifest; it never auto-classifies risk.
- **No AI detected is not a compliance verdict.** The CLI reports *"no local AI signals detected"* — not *"compliant."*

## Usage

```bash
opencomplai scan --manifest system-manifest.json --repo-root .
```

### Options

| Flag | Default | Description |
|------|---------|-------------|
| `--manifest` | `system-manifest.json` | System manifest path |
| `--repo-root` | `.` | Repository root to scan |
| `--commit-ref` | `HEAD` | Commit reference for provenance |
| `--emit-evidence` | on | Append `code_corroboration` ledger event |
| `--enqueue-review` | off | Route major/critical gaps to HITL |
| `--baseline` | — | JSON file with `accepted_categories` |
| `--fail-on` | `none` | CI gating: `none`, `new-major`, `major`, `critical` |
| `--output` | `human` | `human` or `json` |
| `--output-file` / `-f` | — | Write results to `.json` or `.md` file (stdout unchanged) |
| `--ocignore` | repo-root `.ocignore` | Custom scan config path (must be inside `--repo-root`) |
| `--ocignore-bootstrap` / `--no-ocignore-bootstrap` | bootstrap on | Create default `.ocignore` on first scan if missing |

## Opt-in on other commands

```bash
opencomplai init --system-id my-sys --intended-purpose "..." --scan
opencomplai check --manifest system-manifest.json --scan
```

`check --scan` does **not** change exit codes unless `--fail-on` is set.

## Example fixtures

See `examples/sample-system/under-declared-*` for deliberately under-declared manifests.
