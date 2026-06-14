# checker

Run the EU AI Act applicability checker (FLI parity, checker version `fli-2025-07-28`).

## Synopsis

```bash
opencomplai checker [OPTIONS]
```

## Options

| Option | Description |
|---|---|
| `--answers` | JSON file with checker answers (non-interactive / CI replay) |
| `--entity-type` | Skip entity prompt when re-running for another operator role |
| `-o` / `--output` | `human` (default) or `json` |
| `--export-json` | Write full result JSON to path |
| `--export-md` | Write Markdown report |
| `--export-pdf` | Write PDF report (requires `opencomplai-core[reports]`) |
| `--export-all` | Base path for `.json`, `.md`, and `.pdf` exports |
| `--write-manifest` | Write a manifest pre-filled from checker results |
| `--web` | Open the interactive checker in your browser (hosted docs page) |
| `--web --local` | Serve the checker locally and open it — no internet required |

## Examples

```bash
# Interactive wizard
opencomplai checker

# Open the browser-based checker on the docs site
opencomplai checker --web

# Serve the checker locally (fully offline)
opencomplai checker --web --local

# Replay golden answers
opencomplai checker --answers answers.json -o json

# Export all formats
opencomplai checker --answers answers.json --export-all ./reports/eu-ai-act-result

# Pre-fill a manifest from checker results
opencomplai checker --answers answers.json --write-manifest system-manifest.json
```

## Init integration

```bash
opencomplai init --interactive          # runs the checker wizard first
opencomplai init --interactive --skip-checker
```

## Browser-based checker

`--web` opens the [interactive checker page](../getting-started/eu-ai-act-checker.md)
on the docs site. The page runs entirely in your browser — your answers are never
transmitted to any server.

`--web --local` serves the same checker from a temporary local HTTP server and
opens it — useful in air-gapped environments or when you want to verify the
hosted and local behaviour are identical.

The URL opened by `--web` can be overridden with the `OPENCOMPLAI_DOCS_URL`
environment variable.

## Disclaimer

Opencomplai is not affiliated with the Future of Life Institute or the European
Union. Results are informational only — not legal advice. Seek professional legal
counsel for formal compliance decisions.
