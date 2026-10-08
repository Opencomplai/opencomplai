# Mapped-only regimes (DORA and EBA)

`opencomplai gaps --map-to DORA|EBA` adds one column per regime to the EU AI Act gap table, and a
`mapped_regimes` block to the JSON output. Each cell is a **citation**: the DORA chapter or EBA guideline
that covers similar subject matter to that EU AI Act article.

## What "mapped only" means

- It is a pointer, not a verdict. No Met, Partial, Missing or Unverified status is computed for DORA or EBA, and
  the statuses of the EU AI Act rows are identical with and without `--map-to`.
- DORA and EBA are not compliance targets. `--target DORA` still exits 2, and no probe, evaluator or control is
  attached to these rows.
- Without `--map-to` the output is byte-identical to before.

## The review flag

Every row carries `confidence: "low"` and `needs_founder_review: true`, plus a `source`. The identifiers
(chapter and article ranges, EBA guideline numbers) were written from general knowledge and have not been checked
against the primary texts; confirm them before relying on a row. A row that cannot be defended is left out rather
than guessed.

## Rows

| EU AI Act article | DORA | EBA |
|---|---|---|
| Art. 9 | Chapter II (ICT risk management) | |
| Art. 10 | | EBA/GL/2020/06 (loan origination and monitoring) |
| Art. 12 | Chapter III (ICT-related incident management) | |
| Art. 15 | Chapter IV (resilience testing) | EBA/GL/2019/04 (ICT and security risk management) |
| Art. 17 | Chapter II (ICT risk management) | |
| Art. 24 | Chapter V (ICT third-party risk) | |
| Art. 25 | Chapter V (ICT third-party risk) | EBA/GL/2019/02 (outsourcing arrangements) |

## Not covered

- Art. 47 and Art. 48: no counterpart identified.
- Serious-incident reporting (Arts 72/73): not in the control catalog, so no DORA incident-reporting row can
  key on it.

The data lives in `mapped_regimes.json`, separate from `framework_crosswalk.json`. This page is not legal advice.
