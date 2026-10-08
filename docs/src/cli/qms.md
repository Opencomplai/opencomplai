# `opencomplai qms generate`

Write a filled Art. 17(1)(a)-(m) quality-management-system document: one row for each
of the 13 sub-points, with its evidence status, instead of one article-level verdict.

**What:** a per-clause QMS status document (Markdown), plus the same data as JSON.

**When:** after `opencomplai gaps` shows Art. 17 as Missing or Partial, or before you
hand a QMS pack to a reviewer.

**Don't:** read a **Present** row as a legal determination. Status is a
convention-based file probe, the same one `opencomplai gaps` and `opencomplai
recommend` use for Art. 17, so the three commands never disagree.

## Usage

=== "macOS / Linux"
    ```bash
    opencomplai qms generate --manifest system-manifest.json --output qms-document.md
    ```

=== "Windows (PowerShell)"
    ```powershell
    opencomplai qms generate --manifest system-manifest.json --output qms-document.md
    ```

### Options

| Flag | Default | Description |
|------|---------|-------------|
| `--system-id` | *(empty)* | System identifier, written in the document header only |
| `--commit-ref` | `HEAD` | Commit reference for provenance |
| `--repo-root` | `.` | Repository root for the per-clause artifact probes |
| `--manifest` / `-m` | *(none)* | Optional system manifest. Fills clauses (e), (h) and (i), cross-checks EN 18286 and adds the micro-enterprise note. Without it the output is as before. A missing or invalid file exits 2 |
| `--scan-report` | `scan-report.json` | Optional `CorroborationReport`; its hash is cited as evidence when the file exists |
| `--eval-report` | `eval-report.json` | Optional `EvalReport`; its evaluator evidence hashes are cited when the file exists |
| `--scaffold` | off | First write starter clause files under `docs/qms/`. It never overwrites a file, and the starters read as **Unfilled** until you edit them |
| `--output` / `-o` | `qms-document.md` | Path to write the Markdown document |
| `--output-format` | `human` | `human` or `json` |

## Statuses

| Status | Meaning |
|---|---|
| **Present** | A matching file with content was found (heuristic) |
| **Unfilled** | A matching file was found but it is still a scaffold or empty |
| **Missing** | No matching file was found |
| **Unverified** | The probe did not run |

## What `--manifest` adds

Three clauses show what the manifest declares, in a separate **Manifest-declared**
column:

| Clause | Manifest fields |
|---|---|
| (e) Technical specifications and standards applied | `harmonised_standards`, `alternative_solutions` |
| (h) Post-market monitoring system | `post_market_monitoring_plan_ref`, `post_market_monitoring_summary`, `monitoring_approach` |
| (i) Serious-incident reporting procedures | `incident_response_procedure` |

A manifest statement is not file evidence, so it never changes a clause's status or the
counts. A field that is empty or absent leaves its cell empty; nothing is filled in for
you.

The document also has a **Standards** section. It lists EN 18286 from the harmonised
standards catalogue and states whether the manifest's `harmonised_standards` declares
it (`yes`, `no`, or `not checked` without a manifest; `EN 18286`, `EN-18286` and
`EN18286:2026` count as the same). The catalogue records EN 18286 as **published**, not
harmonised: it has not been cited in the Official Journal, so it carries no legal
presumption of conformity. The row is flagged for founder review.

When the manifest's `organisation_size` is `micro`, a **Profile notes** entry says that
Art. 63 lets microenterprises satisfy some QMS elements in a simplified manner, that
this document still keeps all 13 clauses, and that the scope should be confirmed with
counsel. It is low confidence and flagged for founder review. It is never written for
other sizes or when the size is not set.

## Next step

Fill the Missing or Unfilled clauses, then re-run. See [gaps](gaps.md) for the
article-level view and [recommend](recommend.md) for the starter templates.
