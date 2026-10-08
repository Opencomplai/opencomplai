# `opencomplai fria generate`

Draft an Art. 27 fundamental rights impact assessment (FRIA) for a system.

**What:** a draft of Art. 27(1)(a)-(f), filled from what the manifest and the checker
already know, as JSON and Markdown.

**When:** after `opencomplai init` (and ideally `opencomplai checker`), if you deploy a
system that Art. 27 covers.

**Don't:** file it as your assessment. It is an informational draft, not legal advice,
and does not replace the deployer's own assessment or the market-surveillance
notification.

## Usage

=== "macOS / Linux"
    ```bash
    opencomplai fria generate --manifest system-manifest.json --output-dir ./fria
    ```

=== "Windows (PowerShell)"
    ```powershell
    opencomplai fria generate --manifest system-manifest.json --output-dir ./fria
    ```

### Options

| Flag | Default | Description |
|------|---------|-------------|
| `--manifest` / `-m` | `system-manifest.json` | System manifest path. A missing or invalid file exits 2 |
| `--commit-ref` | `HEAD` | Commit reference for provenance |
| `--checker-report` | manifest's `checker_session.report_json_path` | Checker JSON report (from `opencomplai checker --export-json`). Without one, point (c) stays unpopulated |
| `--repo-root` | `.` | Repository root for the Art. 27 control-register probe (`provider_fria`) |
| `--output-dir` | `./fria` | Directory to write the draft to |
| `--output` / `-o` | `human` | `human` or `json` (prints the JSON document) |

## Outputs

Two files in `--output-dir`, named with the draft's id:

- `fria_<id>.json`: the structured draft
- `fria_<id>.md`: the same draft as Markdown

## "Not captured"

Each of the points (a)-(f) is either **populated** from real data or marked **not
captured**, with its source named. A point with nothing behind it is never invented. The
command prints how many of the points were populated, so a thin manifest shows up as a
low count rather than as plausible-looking text.

## Next step

Complete the points marked not captured, then have your counsel review the result. See
[gaps](gaps.md) for the Art. 27 row.
