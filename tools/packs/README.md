# Pack tools

Tracked tools for the framework pack data in `packages/core/src/opencomplai_core/packs/`. Run them from the repository root.

`validate_pack.py` validates any non-EU pack that has a requirements file (`packs/<KEY>/requirements.json`) and checks probe files. It imports `opencomplai_core`.

```sh
uv run python tools/packs/validate_pack.py <KEY> [--strict]
uv run python tools/packs/validate_pack.py --all [--strict]
uv run python tools/packs/validate_pack.py --probes <file.json>
```

It exits 0 with a summary line, or 1 with every problem listed. `validate(key, strict=False)` and `validate_probe_file(path)` return the problem lists.

**Base mode** passes on today's data. Per row: id `<KEY>:<id>`; known fields only; `title` of 1 to 80 characters unless the pack is `public_domain`; `note`, when present, one non-empty line; `default_ttl_days` in 30, 90, 180, 365 or 730; exactly one `attestation` source whose `ref` is the row id (a NIST AI RMF row may have none); other source kinds `artifact`, `evaluator`, `scan`, `manifest`, `record` (`crosswalk` in NIST AI RMF only), never `rule` or `obligation`; `role` absent, `supporting` or `corroborating` (the last only on `artifact`, `evaluator`, `scan`); artifact refs known to `gap_probes.probe_exists`; evaluator refs in `EVALUATOR_REGISTRY`; `scope_out` keys declared for the pack; links into the EU AI Act, ISO 27001 Annex A and ISO 42001 rows resolve. Review flags are never cleared: `needs_founder_review` stays true and a `confidence` above `low` needs a `review_ref`.

**Strict mode** is what a pack card has to satisfy. It adds: every row has `note` and `evidence_class`; in a `restricted` pack the note starts with `Evidence that` or the row has `own_wording: true`; a `machine` or `hybrid` row has a source that is neither the attestation nor `supporting`; an `organisational` row has a one-line `why_attestation` of at most 160 characters; a pack of more than 10 rows uses two or more TTL values; `applicability.json`, when present, loads. Today's packs do not yet pass strict mode.

**Probe files** (`--probes`): the file parses with `parse_probe_file`, every probe has `provenance`, and a probe with a pattern ending `.md`, `.txt`, `.pdf` or `.docx` has `markers`.

For restricted packs (`copyright: restricted`): do not open, search for, or paste the standard's text. Write ids and the existing own-wording notes only.

`packfmt.py` holds `dump(obj) -> str`, the canonical text form of a pack file: two-space indent, arrays of plain strings on one line, a final newline. A pack file written by `dump` reads back unchanged.

`read_verdicts.py` reads a returned framework-mapping review workbook into a verdicts JSON, counts reviewed rows, and checks an apply log. It needs `openpyxl`. The sent workbooks are looked up in `--sent-dir` (default `tools/packs/sent`, not tracked). `--selftest` prints `sent workbooks not present` and exits 0 when that directory is missing.

`test_validate_pack.py` exercises each validator rule on in-memory rows, and strict mode on a temporary pack. `test_pack_tools.py` runs the `dump` round trip on twelve packs. Run both with `uv run pytest tools/packs -q`.

`eu_freeze.sha256` and `nist_freeze.sha256` pin the EU AI Act data, the recommend template map and the CLI golden files, and the NIST data and goldens. Verify with `sha256sum -c tools/packs/eu_freeze.sha256 tools/packs/nist_freeze.sha256`.

## Parity check and pack docs

`parity_check.py` decides, without judgement, whether a pack works like the EU AI Act pack. Passing says the plumbing works, not that the rows are green. It prints one line per capability, `P<n> pass|fail <detail>`, and exits 0 only when all fifteen pass.

```sh
uv run python tools/packs/parity_check.py <KEY> [--json] [--gate] [--write-status]
uv run python tools/packs/parity_check.py --all [--json] [--gate] [--write-status]
```

`--all` covers every pack except `EU_AI_ACT`, which is the reference and is never written. `--gate` makes P15 also require the docs page in `docs/mkdocs.yml`; a later docs card lists the pages there, pack cards do not.

| Capability | What it checks |
| --- | --- |
| P1 | Applicability loads, every outcome has a golden, data files are listed in `pack.json` |
| P2 | `scope_out` keys are declared and a golden shows an excluded row |
| P3 | `evidence_class` and `why_attestation` are valid (strict validator) |
| P4 | Machine and hybrid sources resolve; the machine share meets the target |
| P5 | The empty, scaffolded and evidenced gaps goldens tell evidence from none |
| P6 | Row statuses in the gaps goldens use the four verdict words |
| P7 | `default_ttl_days` values are valid (strict validator) |
| P8 | The empty gate golden exits 1 and names requirement ids |
| P9 | The JUnit, SARIF and summary goldens exist, the JUnit one names this pack |
| P10 | Each machine or hybrid row maps to a template file |
| P11 | One to four scaffold documents resolve, carry the marker and name a probe |
| P12 | The timeline loads; a `none` timeline has a real reason and no dated notes |
| P13 | The report section golden shows the evidence class |
| P14 | Every expected golden and fixture entry exists |
| P15 | The docs page exists and its row table is current (`pack_doc.py <KEY> --check`) |

`--write-status` sets `status` in `pack.json` to `evaluated` when P1 to P15 pass. When they do not and the status was `evaluated`, it goes back to `attestation-led` (`derived` for `NIST_AI_RMF`). Other statuses stay. The file keeps its key order, two-space indent and final newline. A label is `<name> (<status>, <caveat>)` from `pack.json`, so the label follows the status with no code edit.

Order for a pack's last card: run with `--write-status`, regenerate that pack's goldens (the label is in them), run the check again.

`pack_doc.py` keeps the row table of a pack's docs page current:

```sh
uv run python tools/packs/pack_doc.py <KEY>          # rewrite the table
uv run python tools/packs/pack_doc.py <KEY> --check  # exit 1 when stale
```

The page is `docs/src/<docs_page>`; `docs_page` is an optional `pack.json` field and defaults to `frameworks/<key in lower case, - for _>.md`. The table sits between the lines `<!-- rows:start -->` and `<!-- rows:end -->` and lists requirement id, title, evidence class, sources, TTL days, and `mapping not yet reviewed` where `needs_founder_review` is true. A page without both marker lines is an error (exit 2). `render_rows(key)` returns the table text.

## Difference from the old build tables

The old builders (`build.py`, `build_wave2.py`, `regen.py`) are not tracked and must not be run: they would overwrite newer data. The core data files below differ, as parsed JSON, from the same files in the older `fwmap-wt` worktree.

| File | Difference |
| --- | --- |
| `custom_pack.schema.json` | only in this repo |
| `eu_ai_act_principles.json` | 2 of 4 top-level entries differ |
| `framework_crosswalk.json` | 2 of 2 top-level entries differ |
| `gap_article_map.json` | 24 rows here, 23 there; no changed rows |
| `iso_27090.json` | 10 of 31 rows differ |
| `iso_42001.json` | 10 of 65 rows differ |
| `nist_ai_rmf_subcategories.json` | 2 of 2 top-level entries differ |
| `regulatory_timeline.json` | 1 of 2 top-level entries differs |
| `scan_status_artifact.schema.json` | 1 of 9 top-level entries differs |

This repo's copy wins.
