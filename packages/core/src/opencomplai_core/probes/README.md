# Artifact probes as data

A probe says which files count as evidence for a ref and, optionally, what
those files must contain. Probes can be declared in JSON instead of Python.

Two places are read at import time:

- shared probes: `probes/<family>.json` in this directory, read in file-name order;
- pack-local probes: `packs/<KEY>/probes.json`, read for every discovered pack.

## File format

```json
{
  "family": "example",
  "probes": {
    "impact_assessment": {
      "patterns": ["docs/**/impact*.md"],
      "markers": {
        "all": [{"re": "affected (people|groups)", "flags": "i"}],
        "found_label": "an affected-groups section",
        "lacks_label": "affected-groups",
        "noun": "impact assessment",
        "body_only": true,
        "forbid_scaffold": false,
        "select": false,
        "note": ""
      },
      "code_hint": {"re": "\\bimpact_assess\\w*", "flags": "i"},
      "provenance": {
        "source": "heuristic (no legal source): file-name convention",
        "confidence": "low",
        "needs_founder_review": true
      }
    }
  }
}
```

- `patterns` (required): non-empty list of globs, matched against repo paths.
- `markers` (optional): every regex in `all` has to match the file text.
  `flags` uses the letters `i`, `m`, `s`. The three booleans default to false
  and `note` to an empty string; the three labels and `noun` are required.
- `code_hint` (optional): one regex searched in source code.
- `provenance` (optional): `source` and `confidence` are required.

## Clause-document probes

One document, N clauses, one result per clause. Set `"type": "clause_document"`
and give `patterns`, `noun`, `provenance` and `clauses`; there is no `markers`
or `code_hint`.

```json
{
  "family": "example",
  "probes": {
    "example_policy": {
      "type": "clause_document",
      "patterns": ["docs/example_policy.md"],
      "noun": "example policy",
      "provenance": {"source": "heuristic (no legal source)", "confidence": "low"},
      "clauses": {
        "4.1": {
          "title": "Scope",
          "markers": [{"re": "\\bscope\\b", "flags": "i"}]
        }
      }
    }
  }
}
```

- A clause id matches `^[A-Za-z0-9][A-Za-z0-9 ().,/-]*$`. Every clause needs a
  title and at least one marker.
- In the document a clause section starts at the line
  `<!-- clause: <clause id> -->` and runs to the next such line or the end.
- A clause is `present` when its section has at least eight body words, every
  marker matches and it holds no `_fill in_` placeholder; `unfilled` when the
  section exists but fails that; `missing` when there is no anchor for it.
- A pack row cites `<ref>#<clause>` for one clause, or the bare `<ref>` for the
  whole document. A clause row is Unverified without a repo root, Missing
  (0.4) without the file, Partial 0.6 when present, Partial 0.35 when unfilled
  or missing; never Met. The bare row is Partial with a per-clause count.
- A `#` on a plain probe, or an unknown clause, raises ValueError.
  `probe_exists(ref)` answers without raising;
  `clause_document_results(ref, repo_root)` returns one result per clause.
- `registry_snapshot()` lists the probe under its ref with `type`, `noun` and
  `clauses`.

## Names

A shared ref matches `^[a-z][a-z0-9_]*$`. A pack-local ref is the pack key in
lower case, a dot, then a name of the same shape, as in
`iso_iec_42005.impact_assessment`.

A ref that is already registered, in Python or in another file, is an error;
nothing overrides an existing probe.

## Snapshot

`registry_snapshot()` in `gap_probes.py` lists every ref with its settings.
`tests/fixtures/probe_registry_snapshot.json` pins it.
