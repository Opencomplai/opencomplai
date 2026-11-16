# Custom controls pack

A custom controls pack lets an organisation add its own controls next to the built-in frameworks. You
write the controls in one JSON or YAML file and pass it to the CLI with `--custom-pack`. Every control
becomes one row of a further framework, `CUSTOM_<KEY>`, that reads **Unverified** until someone records
an attestation for it.

`--custom-pack` is available from 0.16.0.

**No code runs: a pack is data.** The format has no scripts, expressions, file probes or includes, and
YAML anchors and aliases are refused. A row can only be decided by an attestation, so it is never Met by
default and a pack never reads your repository.

## The file

Either format holds the same fields. This YAML pack:

```yaml
format: opencomplai/custom-pack/v1
key: ACME_AI
label: Acme internal AI controls
controls:
  - id: AC-1
    title: Model inventory reviewed each quarter
    description: The model inventory is reviewed and signed off by the AI governance group.
    default_ttl_days: 90
  - id: AC-2
    title: Customer-facing outputs reviewed before launch
```

and this JSON pack are the same pack:

```json
{
  "format": "opencomplai/custom-pack/v1",
  "key": "ACME_AI",
  "label": "Acme internal AI controls",
  "controls": [
    {
      "id": "AC-1",
      "title": "Model inventory reviewed each quarter",
      "description": "The model inventory is reviewed and signed off by the AI governance group.",
      "default_ttl_days": 90
    },
    {
      "id": "AC-2",
      "title": "Customer-facing outputs reviewed before launch"
    }
  ]
}
```

A file ending in `.json` is read as JSON, any other file as YAML. The JSON Schema of the format ships
with the package as `opencomplai_core/data/custom_pack.schema.json` (`$id`
`https://schemas.opencomplai.dev/custom_pack/v1`).

!!! warning "Validate through the loader, not the schema alone"
    The published schema is a description of the format for editors and other languages. It is looser than
    the loader when a Python regular-expression engine reads it: `$` also matches before a final line
    break, so a `key` of `ACME_AI` followed by a line break passes the schema and is refused by the
    loader. A one-line text is described by two checks, a pattern for the allowed characters and a second
    one that refuses text made only of white space. Python code that accepts a pack must validate it
    through `load_custom_pack` or `CustomPackDocument` in `opencomplai_core.custom_pack`, never through
    the schema alone.

| Field | Required | Rule |
|---|---|---|
| `format` | yes | Exactly `opencomplai/custom-pack/v1`. |
| `key` | yes | 2 to 41 characters, `^[A-Z][A-Z0-9_]{1,40}$`. The framework key is `CUSTOM_<key>`, here `CUSTOM_ACME_AI`. |
| `label` | yes | 1 to 120 characters, one line. |
| `controls` | yes | 1 to 500 controls. |
| `controls[].id` | yes | `^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$`: letters, digits, `.`, `_` and `-`, at most 64 characters, and no colon. Unique in the pack. |
| `controls[].title` | yes | 1 to 200 characters, one line. |
| `controls[].description` | no | Up to 2000 characters; may run over several lines. Default: empty. |
| `controls[].default_ttl_days` | no | Whole number of days from 1 to 3650 after which an undated attestation is reported as stale. Default: 365. |

Any other key is refused, at any level, and so is a mapping that names the same key twice. Text fields
hold no control characters (except that a `description` may hold a tab and line breaks) and none of the
characters that hide, reorder or show as nothing: line and paragraph separators, direction marks and
overrides, zero-width characters (the zero-width joiners too, so text that needs one cannot be used), the
soft hyphen, variation selectors, filler characters, the Arabic number signs and end-of-text marks, the
interlinear annotation marks, the Braille blank, the format controls of shorthand, musical notation and
Egyptian hieroglyphs, and the tag characters. The list is fixed: a format character added to Unicode later
is not on it. A `description` may run over several lines, with line breaks written as LF or CRLF; a bare
carriage return is refused.
The file may be at most 1 048 576 bytes. A key that is already registered, or a duplicate control id, is
refused.

## Row ids and what a row says

A requirement id is `CUSTOM_<key>:<id>`, for example `CUSTOM_ACME_AI:AC-1`. Each row:

- takes an attestation and nothing else, so it is **Unverified** until attested and never Met by default;
- reads **Unverified** with its confidence not assessed while no attestation is recorded, and **Met**
  once one is;
- counts as an ordinary framework row: it appears in `gaps` output, in the artifact's
  `framework_reports` and in `report`.

A custom pack says what your organisation asks of itself. It is not an audit, a certification or a legal
assessment.

## Running it

```bash
opencomplai gaps --custom-pack acme-controls.yaml
opencomplai check --with-gaps --custom-pack acme-controls.yaml
```

The pack is assessed as a further framework next to the manifest's targets (the EU AI Act is always
evaluated). A file that cannot be used prints `Error: custom pack: <reason>` and exits `2`. The reason
never repeats the file's own text.

`report` needs no flag. It renders the `framework_reports` already in the artifact, so a custom section
shows up there. The artifact holds ids and statuses but not control titles, so the title column of a
custom section reads a dash.

## Attesting a control

Record an attestation the way you do for any other framework, under `framework_inputs.CUSTOM_<KEY>.attested`
in the manifest, keyed by the full requirement id:

```json
{
  "framework_inputs": {
    "CUSTOM_ACME_AI": {
      "attested": {
        "CUSTOM_ACME_AI:AC-1": {
          "statement": "Reviewed on 12 October 2026; minutes in the governance wiki.",
          "attested_by": "Jane Doe",
          "attested_at": "2026-10-12"
        }
      }
    }
  }
}
```

An [attestation bundle](../frameworks/more-packs.md#attestation-bundles) carrying `CUSTOM_ACME_AI`
records works the same way. An attestation whose id is not a control of the pack exits `2` when it is in
the manifest, and is ignored with a warning when it comes from a bundle.

A run without `--custom-pack` still works for a manifest or bundle that carries custom attestations: the
`CUSTOM_*` entries are left alone, and the pack is simply not assessed.

## Gating on a pack

A custom pack fails a check only when you gate on it, like any other non-EU framework. List its key in
`--gate` or in `opencomplai.yaml`, and load the pack in the same run:

```yaml
gate:
  frameworks: [CUSTOM_ACME_AI]
  fail_on: unverified
```

With `fail_on: unverified`, a control with no current attestation fails the check, because every row of a
custom pack can only be decided by an attestation. With the default (`missing`) or `partial`, an
unattested control never fails, so `check` and `gaps` print a warning on stderr when a gated custom pack
is paired with either. Gating on `CUSTOM_ACME_AI` in a run that does not load the pack exits `2` and
says to load it with `--custom-pack`, the same as gating on any unknown framework.
