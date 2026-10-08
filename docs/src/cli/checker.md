# checker

Run the EU AI Act applicability checker (checker version `checker-2026-10-05`).

## Synopsis

=== "macOS / Linux"
    ```bash
    opencomplai checker [OPTIONS]
    ```

=== "Windows (PowerShell)"
    ```powershell
    opencomplai checker [OPTIONS]
    ```

## Options

| Option | Description |
|---|---|
| `--answers` | JSON file with checker answers (non-interactive / CI replay) |
| `--entity-type` | Operator role (`provider`, `deployer`, `distributor`, `importer`, `product_manufacturer`, `authorised_rep`); repeat the flag for each role. The entity question is skipped. An unknown value exits 2 |
| `-o` / `--output` | `human` (default) or `json` |
| `--export-json` | Write full result JSON to path |
| `--export-md` | Write Markdown report |
| `--export-pdf` | Write PDF report (requires `opencomplai-core[reports]`) |
| `--export-all` | Base path for `.json`, `.md`, and `.pdf` exports |
| `--write-manifest` | Write a manifest pre-filled from checker results |
| `--intended-purpose` | With `--write-manifest`: what the system does, written to `intended_purpose` (prompted when omitted) |
| `--web` | Open the interactive checker in your browser (hosted docs page) |
| `--web --local` | Serve the checker locally and open it — no internet required |

## Examples

=== "macOS / Linux"
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
    opencomplai checker --answers answers.json --write-manifest system-manifest.json --intended-purpose "Screens job applicants"
    ```

=== "Windows (PowerShell)"
    ```powershell
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
    opencomplai checker --answers answers.json --write-manifest system-manifest.json --intended-purpose "Screens job applicants"
    ```

## Several roles

A system can have more than one Article 3 role (a provider that also deploys
it). Repeat `--entity-type`: the checker runs once per role and the results are
merged (obligations are the union, listed once each). Each role also gets one
line of rationale, written from the checker's own result, in the Markdown and
JSON exports and in `checker_session.rationale`.

```bash
# First run creates the manifest (operator_roles and obligation_ids are recorded)
opencomplai checker --answers answers.json --entity-type provider --entity-type deployer   --write-manifest system-manifest.json --intended-purpose "Screens job applicants"

# Later run on the same file appends another role; nothing else is overwritten
opencomplai checker --answers answers.json --entity-type importer --write-manifest system-manifest.json
```

When the manifest already exists, `--write-manifest` appends: `system_id`,
`intended_purpose` (unless `--intended-purpose` is given), other fields and key
order stay as they were, `operator_roles` and `checker_session.obligation_ids`
grow, and `checker_session.verdict` keeps the more severe of the old and new
tier. A manifest that is not valid JSON, or not an object, exits 2 and is left
untouched. Without `--entity-type`, no `operator_roles` is written.

## Manifest fields

`--write-manifest` records the checker's tier label (`prohibited_practice`,
`high_risk_ai_system`, `limited_risk_transparency`, `general_purpose_ai_model`,
`in_scope_ai_system` or `out_of_scope`) as `checker_session.verdict`, and
writes your `--intended-purpose` text to `intended_purpose`, which the EU rules
classify. `opencomplai check` fails a `prohibited_practice` or
`high_risk_ai_system` verdict even when the purpose text matches no rule; see
[check](check.md).

## Init integration

=== "macOS / Linux"
    ```bash
    opencomplai init --interactive          # runs the checker wizard first
    opencomplai init --interactive --skip-checker
    ```

=== "Windows (PowerShell)"
    ```powershell
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

Opencomplai is not affiliated with the European Union. Results are informational
only — not legal advice. Seek professional legal counsel for formal compliance
decisions.
