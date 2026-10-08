# Backlog order

`--sort priority` reorders gap rows so the ones to work on first come first. It changes how rows are
listed, nothing else.

## The order

With `opencomplai gaps --sort priority`, and the same option on
[`recommend`](../cli/recommend.md) and [`report`](../cli/report.md), rows are sorted by:

1. rows that still need work before rows that are `met`;
2. the earliest known application date of the article, rows with no known date last;
3. status, worst first (`missing`, then `partial`, then `unverified`);
4. effort, smallest first (S, M, L);
5. the original article order, as the tie-break.

The default, `--sort article`, keeps the article order every earlier release used.

## Where the inputs come from

| Input | Source |
|---|---|
| Deadline | The per-article application date in the regulatory timeline data. The sorter never writes a date and ignores entries whose date is unknown. |
| Status | The row's own gap status. |
| Effort | A maintainer's rough engineering estimate stored with the remediation templates. It is an ordering hint, not a compliance claim, and not a time estimate for your system. |

Timeline dates that are still unverified carry low confidence and a review flag in the timeline data; see
the `source`, `confidence` and `needs_founder_review` fields there. No clock is read, so no output contains
today's date or a number of days remaining.

## What it never changes

- **Verdicts.** Statuses are computed before sorting and are identical with either order.
- **Controls.** The control register and its order are built from the unsorted rows.
- **Exit codes.** `gaps`, `recommend` and `report` never gate, and `check` does not sort.
- **The default output.** Without `--sort priority`, output is unchanged.

`gaps --output json --sort priority` adds a `backlog` block next to the report: each row that still needs
work with its `rank`, `article`, `status`, `deadline` (or `null`) and `effort`. The NIST AI RMF table keeps
subcategory order, and says so.
