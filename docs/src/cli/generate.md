# generate

Write a document or an export from the manifest or from a compliance artifact. Four generators sit under one group: `generate model-card`, `generate impact-assessment`, `generate oscal` and `generate common-controls`.

Generators move data and never gate. Each exits `0` when it wrote its output and `2` when its input is unreadable or invalid. None of them returns `1`, none changes a verdict, and nothing is sent anywhere.

## generate model-card

Write a Markdown model card with YAML front matter from the system manifest. A section the manifest has no data for says `Not captured in the system manifest.`; nothing is invented.

=== "macOS / Linux"
    ```bash
    opencomplai generate model-card --manifest manifest.json --output MODEL_CARD.md
    ```

=== "Windows (PowerShell)"
    ```powershell
    opencomplai generate model-card --manifest manifest.json --output MODEL_CARD.md
    ```

| Option | Default | Description |
|---|---|---|
| `--manifest`, `-m` | `manifest.json` | System manifest JSON. |
| `--output`, `-o` | `MODEL_CARD.md` | Path to write the model card. |
| `--output-format` | `human` | `human` prints one line; `json` prints the system id, the commit reference, the output path, each section with its source and whether it was filled, the metrics and the provenance list. |

### Field mapping

| Section | Manifest field |
|---|---|
| Intended use | `intended_purpose` |
| Model details | `model_architecture` |
| Training data | `training_data_description` |
| Evaluation | `performance_metrics`, `metrics_appropriateness_rationale` |
| Limitations | `known_limitations` |
| Foreseeable misuse | `foreseeable_misuse` |
| Human oversight | `human_oversight_measures` |
| Monitoring | `monitoring_approach` |
| Provenance | `imported_evidence` |

The metrics are also written to the front matter as model-index results, one result per dataset (a metric key `dataset/metric` names its dataset), in the keys the model card importer reads, so they read back unchanged.

Values listed under Provenance come from imported evidence. They are provider-declared, not verified, and the card says so.

### What stays for you

The card is a draft that records what the manifest declares. Add what the manifest does not hold, and check each declared value against your own records before you publish it.

## generate impact-assessment

Write a fill-in impact assessment draft as `impact_assessment_<kind>.md` and `impact_assessment_<kind>.json`, pre-filled from the manifest. Not legal advice and not an assessment by itself: it is a structured draft for the people who carry out the assessment.

=== "macOS / Linux"
    ```bash
    opencomplai generate impact-assessment --kind ai-system --manifest manifest.json --output-dir assessments
    ```

=== "Windows (PowerShell)"
    ```powershell
    opencomplai generate impact-assessment --kind ai-system --manifest manifest.json --output-dir assessments
    ```

| Option | Default | Description |
|---|---|---|
| `--kind` | required | `ai-system` or `dpia`. Any other value exits `2`. |
| `--manifest` | `manifest.json` | System manifest to pre-fill from. |
| `--output-dir` | `assessments` | Directory for the `.md` and `.json` files. It is created when missing. |

### Kinds

- `ai-system` has one section per row of the `ISO_IEC_42005` framework pack, read from the pack at run time. Each section carries the row's title and guidance.
- `dpia` has a header block (controller, processors, data protection officer, prior consultation under Art. 36) and four sections for GDPR Art. 35(7)(a) to (d): processing and its purpose, necessity and proportionality, risks to the people concerned, and measures that address the risks.

### Field mapping

A section is pre-filled when a keyword in its title matches, from these manifest fields:

| Keyword in the section title | Manifest field |
|---|---|
| purpose | `intended_purpose` |
| data | `training_data_description`, `input_data_specifications` |
| risk, misuse | `known_limitations`, `foreseeable_misuse` |
| oversight, measure | `human_oversight_measures` |
| monitor | `monitoring_approach` |
| incident | `incident_response_procedure` |

The match is by keyword on the title, not a semantic mapping, so a row can stay unfilled even when the manifest holds related text.

### What stays for you

Every cell the manifest cannot fill reads `_fill in_`. Every section has an Owner cell, and it always reads `_fill in_`. The document ends with the line "Draft for review. Not legal advice and not an assessment by itself." Complete each cell, name an owner, and have the assessment reviewed by the people responsible for it.

## generate oscal

Write one OSCAL 1.1.2 assessment-results JSON document from a compliance artifact written by `opencomplai check --with-gaps`.

=== "macOS / Linux"
    ```bash
    opencomplai generate oscal compliance-artifact.json --out assessment-results.json
    ```

=== "Windows (PowerShell)"
    ```powershell
    opencomplai generate oscal compliance-artifact.json --out assessment-results.json
    ```

| Option | Default | Description |
|---|---|---|
| `ARTIFACT` (argument) | required | Path to a `compliance-artifact.json`. An artifact without a gap report exits `2`. |
| `--out` | stdout | Write the document to this file (UTF-8, LF line endings) instead of stdout. |

The output is not validated against the NIST OSCAL schema. Validate it with an OSCAL tool before you hand it to one.

### Status mapping

The document has one result per framework (the EU AI Act first, then each key in `framework_reports`) and one finding per requirement row. Identifiers are derived from the system id, the commit reference and the path, and the document holds no clock reading of its own, so the same artifact gives the same bytes.

| Row status | OSCAL target state |
|---|---|
| `met` | `satisfied` |
| anything else (`partial`, `missing`, `unverified`) | `not-satisfied` |

The exact status stays in the `opencomplai-status` property of each finding, next to the requirement id, the source, the confidence label and the evidence reference. Rows that do not apply, or that are excluded, are listed under `exclude-controls` with their reason and get no finding.

### What stays for you

The document carries no assessment plan (`import-ap` points at `#no-assessment-plan`). A binary OSCAL state cannot express Partial, so read the property when the difference matters.

## generate common-controls

List the evidence sources that framework pack rows cite, with the rows that share each one.

=== "macOS / Linux"
    ```bash
    opencomplai generate common-controls --artifact compliance-artifact.json --min-frameworks 2
    ```

=== "Windows (PowerShell)"
    ```powershell
    opencomplai generate common-controls --artifact compliance-artifact.json --min-frameworks 2
    ```

| Option | Default | Description |
|---|---|---|
| `--artifact` | none | A `compliance-artifact.json`. With it, each row carries the status the artifact holds for that row. |
| `--output-format` | `human` | `human` prints a table with `ref`, `kind`, `frameworks` and `rows`; `json` prints the full list. |
| `--min-frameworks` | `1` | Keep only controls cited by at least this many frameworks. The minimum is `1`. |

### Mapping

A common control is one pair of source kind and reference that rows of one or more packs cite. The kinds listed name a piece of evidence: `artifact`, `evaluator`, `scan`, `manifest` and `record`. Attestation, rule, obligation and crosswalk sources are left out.

Each row shows its framework, requirement id, title and role. With `--artifact`, a row also shows the status the artifact holds for that requirement id; a row the artifact does not hold has no status and is not counted as credited.

### What stays for you

A shared evidence source is not a shared verdict. One piece of evidence can satisfy one framework's row and fall short of another's, and no status is copied from one row to another. Read each row against its own requirement.
