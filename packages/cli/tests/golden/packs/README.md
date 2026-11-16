# Per-pack goldens

One directory per framework pack, named by the pack key. The fixtures that
produce them live in `packages/core/tests/fixtures/packs/<KEY>/`.

```
packs/<KEY>/
  gaps_empty.json          gaps_empty.txt
  gaps_scaffolded.json     gaps_scaffolded.txt
  gaps_evidenced.json      gaps_evidenced.txt
  gate_empty.txt
  check_reports.junit.xml  check_reports.sarif.json  check_reports.summary.md
  report_section.html
  applicability_<outcome>.json     one per fixture applicability manifest
```

Commands, run in a temp copy of the fixture repo:

- `gaps --target <KEY> --repo-root . --output json`, and the human form
- `check --target <KEY> --gate <KEY> --gate-fail-on missing --repo-root .` on
  `empty/`; `gate_empty.txt` is `exit=<code>` then the failed requirement ids,
  one per line
- the same `check` command on `empty/` with `--with-gaps` (the artifact then
  carries the per-row verdicts) and `--report-junit r.xml
  --sarif-output r.sarif --summary-md r.md`; the three files are
  `check_reports.junit.xml`, `check_reports.sarif.json` and
  `check_reports.summary.md`, each failed pack row listed on its own
- `gaps --target <KEY> --repo-root . --output json` on `evidenced/`; the pack's
  `FrameworkReport` is read from `payload.frameworks.<KEY>` and
  `render_framework_section` of it is `report_section.html`
- `scope <KEY> --output json` on each applicability manifest

Output goes through the same normalisation as the flat goldens (timestamps,
versions, temp paths and commit ids are masked).

A pack with fixtures and no golden directory fails, and so does a golden
directory without fixtures.

## Rule

A pack card edits only its own two directories: `golden/packs/<KEY>/` here and
`packs/<KEY>/` under the core fixtures. It never edits the shared test or the
flat files in `golden/`.

## Update

```sh
OPENCOMPLAI_UPDATE_PACK_GOLDEN=<KEY> uv run pytest packages/cli/tests/test_pack_goldens.py -k <KEY>
```

This rewrites that key's directory and nothing else. It is not the variable of
the flat EU AI Act and NIST goldens, which are never regenerated.
