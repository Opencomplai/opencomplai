# Detect AI in your code — the corroboration scanner

The `opencomplai scan` command cross-checks your manifest's declared
`intended_purpose` against the AI capability signals actually present in the
repository — dependencies, imports, model artifacts, API endpoints.

## Two honesty rules

!!! warning "Read these before using the scanner"
    1. **The declaration stays authoritative.** The scanner never auto-classifies
       risk or edits your manifest. It surfaces discrepancies for a human to reconcile.
    2. **"No local AI signals detected" is not a compliance verdict.** It means
       the scanner found nothing locally — not that the system is compliant.

## Quick start

```bash
opencomplai scan --manifest system-manifest.json --repo-root .
```

Point `--repo-root` at the directory that actually contains your model code,
inference imports, and dependencies.

## `.ocignore` scan configuration {#ocignore}

The scanner reads a repo-root [`.ocignore`](https://github.com/opencomplai/opencomplai/blob/main/.ocignore)
file for **exclusion patterns** and **inventory limits**. It does **not** read
`.gitignore` at scan time — on first `opencomplai scan`, the CLI can create a
default `.ocignore` and optionally merge non-comment lines from `.gitignore` once.

### Pattern subset (v1)

| Supported | Not supported (v1) |
|-----------|-------------------|
| `fnmatch` globs (`*.pem`, `dist/`) | Negation (`!pattern`) |
| Trailing `/` for directories (`node_modules/`) | `**` recursive globs |
| Basename match (`Makefile` matches any depth) | Anchored paths (`/abs/path`) |

Examples:

| Pattern | Matches |
|---------|---------|
| `node_modules/` | `node_modules/pkg/index.js` |
| `*.pem` | `certs/server.pem` |
| `build` | `build` or `out/build` (basename) |

### Limits (`[limits]` block)

`0` means **no cap** for numeric limits. Template defaults are unlimited.

| Key | `0` / `false` | Non-zero |
|-----|---------------|----------|
| `max_files` | No file-count cap | Stop walk |
| `max_bytes_per_file` | No per-file cap | Skip oversized files |
| `max_total_bytes` | No cumulative cap | Stop walk |
| `skip_binary` | Include binaries | Skip non-model binaries |
| `max_symlink_depth` | Unlimited resolution | Block deeper symlinks |
| `max_notebook_cells` | Parse all cells | Truncate notebook parsing |

CI-safe preset (paste into `.ocignore` — not the default):

```gitignore
[limits]
max_files = 10000
max_bytes_per_file = 2097152
max_total_bytes = 104857600
skip_binary = true
```

Use `--no-ocignore-bootstrap` in CI when `.ocignore` is committed. Use
`--ocignore PATH` for a custom config file (must live inside `--repo-root`).

Progress output summarizes skips, e.g. `673 files inventoried (18 ignored, 5 over limit)`.

## The under-declared fixtures

The repo ships three deliberately under-declared example systems under
`examples/sample-system/`. Each has a manifest that understates the actual
AI capability in the code:

| Fixture | Declares | Scanner detects | Why |
|---|---|---|---|
| `under-declared-chatbot` | `customer support chatbot` | `biometric` | imports `face_recognition` |
| `under-declared-scoring` | `rule-based scoring` | `employment`, `essential_services`, `law_enforcement` | pickled classifier + `rank_applicants()` |
| `under-declared-analytics` | `analytics dashboard` | `essential_services` | `chromadb` + `sentence-transformers` |

Run the chatbot fixture:

```bash
opencomplai scan \
  --manifest examples/sample-system/under-declared-chatbot/system-manifest.json \
  --repo-root examples/sample-system/under-declared-chatbot \
  --no-emit-evidence
```

Expected output:

```
Code Corroboration Scan
  severity:     major
  declared:     (none)
  detected:     biometric
  discrepancies: biometric
    - requirements.txt:1
    - requirements.txt:2
    - src/face.py:1

  Declaration is authoritative; confirm or update intended_purpose.
```

A folder with no AI signals stays honest:

```
Code Corroboration Scan
  severity:     none
  declared:     (none)
  detected:     (none)
  No local AI signals detected — not a compliance verdict.
```

## Opt-in on `init` and `check`

The scanner is **opt-in** and never changes exit codes unless you set `--fail-on`:

```bash
# Run scanner after writing the manifest
opencomplai init --system-id my-sys --intended-purpose "..." --scan

# Corroborate during the compliance gate
opencomplai check --scan

# CI: fail the gate only when NEW major discrepancies appear
opencomplai check --scan --fail-on new-major
```

## Severity levels

| Severity | Meaning |
|---|---|
| `none` | No discrepancy between declared and detected |
| `minor` | Detected capability plausibly covered by declaration |
| `major` | Clear gap — declaration likely needs updating |
| `critical` | High-confidence undeclared high-risk capability |

## `--fail-on` CI gating

| Value | Effect |
|---|---|
| `none` (default) | Always exits `0` — advisory only |
| `new-major` | Exits `1` only when a **new** major/critical gap appears vs. baseline |
| `major` | Exits `1` on any major or critical gap |
| `critical` | Exits `1` on critical gaps only |

Use a baseline file to suppress already-accepted gaps:

```bash
# Accept current gaps into a baseline
echo '{"accepted_categories": ["biometric"]}' > scan-baseline.json

# Future runs only fail on NEW gaps not in the baseline
opencomplai check --scan --fail-on new-major --baseline scan-baseline.json
```

## Service-backed mode (Docker stack)

When `OPENCOMPLAI_API_URL` is set, `scan` writes a `code_corroboration`
ledger event to the evidence vault and can route major/critical gaps to the
HITL review queue:

```bash
OPENCOMPLAI_API_URL=http://localhost:8080 \
  opencomplai scan --manifest system-manifest.json --repo-root . --enqueue-review
```

## Further reading

- [scan CLI reference](../cli/scan.md) — all flags
- [Customer workflow §2b](../guides/customer-workflow.md) — where scan fits in the full compliance lifecycle
