# CI code scanning (SARIF)

`opencomplai scan --sarif-output` emits scan evidence as a [SARIF 2.1.0](https://sarifweb.azurewebsites.net/)
document, so AI-signal findings can appear in GitHub's **Security → Code scanning**
tab alongside your other static-analysis tools.

!!! info "Corroboration-only — SARIF results never change `scan`'s exit code"
    SARIF is a **pure export format**. Writing it does not alter scan behavior, and the
    manifest's declared `intended_purpose` remains the sole compliance authority — a
    SARIF finding is a corroboration signal for a human/reviewer to look at, not a
    pass/fail verdict in itself. Gating still goes through `--fail-on`, exactly as
    without `--sarif-output`.

## Usage

=== "macOS / Linux"
    ```bash
    opencomplai scan --manifest system-manifest.json --repo-root . --sarif-output results.sarif
    ```

=== "Windows (PowerShell)"
    ```powershell
    opencomplai scan --manifest system-manifest.json --repo-root . --sarif-output results.sarif
    ```

This writes `results.sarif` **in addition to** the normal scan output — it does not
replace `--output json`/`--output-file`.

## GitHub Actions: upload to the Security tab

```yaml
- name: Opencomplai scan (SARIF)
  run: |
    pip install opencomplai
    opencomplai scan --manifest system-manifest.json --repo-root . --sarif-output results.sarif

- name: Upload SARIF to GitHub code scanning
  uses: github/codeql-action/upload-sarif@v3
  with:
    sarif_file: results.sarif
```

The `upload-sarif` step requires `security-events: write` permission on the workflow
job:

```yaml
permissions:
  security-events: write
```

## What ends up in the SARIF document

Every `EvidenceItem` from the scan's `CorroborationReport` becomes one SARIF `result`:

| SARIF field | Source |
|---|---|
| `ruleId` | `<detector_id>/<signal_category>`, e.g. `DET_FRAMEWORK_AST_V1/agent_framework` |
| `level` | Derived from `EvidenceItem.confidence` — a heuristic severity hint, not a compliance verdict |
| `message.text` | Category, evidence kind, rationale code, and confidence, plus a reminder that this is corroboration-only |
| `locations` | File path + line number parsed from the evidence's recorded location(s) |
| `properties.evidence_id` / `.scope` / `.reachability` | Passed through unchanged from the evidence item |

`tool.driver.rules` lists one rule definition per unique `<detector_id>/<category>` pair
that actually fired, so GitHub's Security tab shows a distinct rule per detector/category
combination rather than one generic "AI signal" rule.

## Combining with `--framework-detectors`

SARIF export picks up whatever evidence the scan produced — including
[`--framework-detectors`](../cli/scan.md#framework-object-detection---framework-detectors)
findings, if enabled:

=== "macOS / Linux"
    ```bash
    opencomplai scan --manifest system-manifest.json --repo-root . \
      --framework-detectors --sarif-output results.sarif
    ```

=== "Windows (PowerShell)"
    ```powershell
    opencomplai scan --manifest system-manifest.json --repo-root . --framework-detectors --sarif-output results.sarif
    ```

See the [scan CLI reference](../cli/scan.md) for the full flag table.
