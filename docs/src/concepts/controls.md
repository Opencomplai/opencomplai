# Controls lifecycle

The control register turns each `opencomplai gaps`/`check` run's per-article
verdicts into a **persistent** record: one `ControlInstance` per obligation,
that survives across runs, can be assigned an owner and a TTL, and tracks
whether its evidence is still fresh. This is the "missing/stale evidence
queue" the round's honesty positioning refers to — it is **not** a new
database table bolted on for the occasion, it's a view over the existing
review-item machinery plus one new persisted model.

Requires an evidence vault (`OPENCOMPLAI_VAULT_URL`). Without one, `gaps` and
`check` behave exactly as they did before this feature existed — see
[Vault-less mode](#vault-less-and-engine-less-mode) below.

## The model

A `ControlInstance` binds `{tenant_id, system_id, obligation_id}` to an
owner, a state, and the evidence backing it.

| Field | Meaning |
|---|---|
| `control_id` | Deterministic identity: `sha256(tenant_id\|system_id\|obligation_id)[:32]`. Re-deriving a control for the same triple across runs upserts the same row instead of creating a duplicate. |
| `obligation_id` / `article_ref` | For gaps-derived controls, both equal the article string (`"Art. 9"`, etc.) — one control per mapped article. |
| `owner` | Accountable person, set via `opencomplai controls assign`. Never set automatically. |
| `state` | One of `satisfied`, `evidence_missing`, `evidence_stale`, `pending_review`, `waived`. |
| `evidence_refs` | Evidence-vault content hashes backing this control. |
| `ttl_days` | Per-control override for the freshness window. `null` falls back to the catalog default for this article. |
| `last_assessed_at` / `last_evidence_at` / `due_at` | Timestamps used to compute staleness. |
| `waiver_rationale` | Set by a manual waiver, or by a manifest exclusion (`framework_inputs.<FW>.excluded`). |
| `waiver_source` | `exclusion` or `manual` for a waived control; `null` on legacy rows, which are treated as manual. |

## States

| State | Meaning |
|---|---|
| `satisfied` | The mapped article read `MET` on the run that derived this control, or a human attached evidence directly. A scan detection alone never produces `MET`, so it never produces `satisfied`. |
| `evidence_missing` | The mapped article read `PARTIAL`, `MISSING`, or `UNVERIFIED` and there is no surviving evidence to fall back on. |
| `evidence_stale` | Evidence exists but its TTL has expired, or the manifest changed in a way that invalidates it (see [Freshness](#freshness) below). |
| `pending_review` | Reserved for the review-queue integration; not set by the current derivation path. |
| `waived` | A human explicitly waived this control. Never overwritten by an automated `gaps`/`check` run. |

## Persistence

Control instances and manifest fingerprints live in **evidence-vault**
(migration `0007_add_control_instances.py`) — the only service in this stack
with a real Postgres deployment, so this feature adds no new service and no
second migration chain. Both new tables (`control_instances`,
`manifest_fingerprints`) are tenant-scoped with Postgres row-level security,
following the same pattern as the pre-existing evidence tables: `tenant_id`
column, `FORCE ROW LEVEL SECURITY`, and a policy scoped to
`current_setting('app.tenant_id')`.

The same migration adds four provenance columns to the existing
`evidence_objects` table: `source`, `source_version`, `collected_at`,
`valid_until`. These are what let a control's freshness be computed from the
evidence itself, not just from when the control row was last touched.

## Derivation from `gaps`

Every `opencomplai gaps` invocation (and `opencomplai check --with-gaps`)
that has a vault configured upserts one control per article row in the gap
report:

- **`MET`** → `satisfied`, with the row's evidence hash appended to
  `evidence_refs` (existing refs are kept, not replaced). A scan detection alone
  never reads `MET`, so it never produces a `satisfied` control.
- **`PARTIAL` / `MISSING` / `UNVERIFIED`** → normally downgrades to
  `evidence_missing`, **except**: if the existing control is already
  `satisfied` with evidence a human attached manually, and the new row's
  source is a heuristic artifact probe or its status is `UNVERIFIED`, the
  manually-attached evidence survives untouched. A heuristic probe or an
  unresolved obligation is not treated as a hard signal that previously
  attached evidence stopped applying — only evidence age (TTL) or a real
  manifest change can stale it out. A hard signal (a failing rule,
  obligation, scan, or evaluator row) still downgrades the control
  regardless of manually-attached evidence.
- A manual waiver is never overwritten by an automated run. A waiver derived
  from a manifest exclusion lifts when the exclusion is removed from the
  manifest: the control is re-derived and its rationale cleared.
- `owner`, `ttl_days`, and `waiver_rationale` are always carried forward
  verbatim from the existing row; derivation never sets or clears them.

## Freshness — read-time only, no cron

There is no scheduler, cron job, or background worker anywhere in this
feature. Staleness is computed **at read time**, by two pure detectors:

- **TTL expiry** — a `satisfied` control's evidence expiry is computed from
  (in order of precedence) the referenced evidence objects' `valid_until`,
  then their `collected_at` plus the effective TTL, then the control's own
  `due_at`, then `last_evidence_at` plus the effective TTL. If none of those
  resolve, the control never goes stale from age alone. Effective TTL
  resolves as: the control's own `ttl_days` override, else the catalog
  default for its article, else no TTL.
- **Manifest change** — a stable fingerprint (`sha256` over a fixed subset of
  manifest fields: `intended_purpose`, `model_architecture`,
  `high_risk_presumption`, `training_data_description`, `operator_role`) is
  compared against the last stored fingerprint for the system. If it
  changed, every `satisfied` control whose evidence predates this
  assessment run is flagged `evidence_stale`.

`opencomplai controls list` and `controls status` run the TTL check inline,
every time they're invoked — the state you see is always current at read
time, never a cached value that could silently drift.

### Catalog TTL defaults

| Article(s) | Default TTL |
|---|---|
| Art. 9, Art. 10 | 90 days |
| Art. 12 | 30 days |
| Art. 43, Art. 47, Art. 48 | 365 days |
| Everything else in the catalog | 180 days |

Override per control with `opencomplai controls assign ... --ttl-days N`.

## Reassessment trigger

`POST /v1/controls/reassess` (risk-engine) is what actually applies the
manifest-fingerprint detector server-side, patches newly-stale controls to
`evidence_stale`, enqueues one `ReviewItem` per stale control (deduplicated
by a deterministic key, so re-running against unchanged evidence never
double-enqueues), and stores the latest fingerprint.

The CLI calls this endpoint automatically after every vault sync — from
`opencomplai gaps` and from `opencomplai check --with-gaps` — **only when**
`OPENCOMPLAI_RISK_ENGINE_URL` is also set. If it isn't, the CLI still stores
the fingerprint directly (so the next reassessment has something to compare
against) and prints `Reassessment skipped: OPENCOMPLAI_RISK_ENGINE_URL not
set`.

## The queue is a view, not a new table

Stale controls surface through the **existing** `ReviewItem` machinery — the
same queue used for evaluator failures and modification-trap reviews — with
two reasons specific to this feature:

| `ReviewReason` | When |
|---|---|
| `EVIDENCE_STALE` | TTL-expiry staleness. |
| `MANIFEST_CHANGE` | Manifest-fingerprint staleness. |

Each enqueued item carries `assigned_to` (mirrors the control's `owner`) and
`expires_at` (the control's effective TTL in hours, or 72 hours if the
control has no TTL). There is no separate "missing/stale evidence queue"
table — it's the same review queue, filtered.

## The artifact `controls` block

`ScanStatusArtifact.controls` is an **optional** block (`ControlsSummary`)
that appears only when `check --with-gaps` ran with a vault configured. It
carries a zero-filled per-state count and one compact row per control
(`control_id`, `article_ref`, `state`, `owner`, `due_at`). When no vault is
configured, the field is simply absent — existing consumers of the artifact
schema that don't expect it are unaffected.

## Halt / resume interaction

A system that `check` has moved to `HALTED_PENDING_REVIEW` (trap detected, or
an unresolved HIGH-risk corroboration gap) still has its controls derivable
and listable — halting is a dossier-generation gate
(`opencomplai docs generate` for that system exits `4`), not a control-register
lock. See [Exit codes](../cli/exit-codes.md#halt--resume-gate-opencomplai-check-opencomplai-docs-generate)
for the full halt/resume contract.

## Vault-less and engine-less mode

- **No `OPENCOMPLAI_VAULT_URL`**: `gaps` and `check` run exactly as they did
  before this feature existed — no control derivation, no sync attempt, no
  extra output. Every `opencomplai controls` subcommand refuses immediately
  with exit `2` and a message explaining the register has no vault-less
  local fallback.
- **Vault configured, no `OPENCOMPLAI_RISK_ENGINE_URL`**: derivation and
  sync still run (TTL staleness is still computed by `controls list`/`status`
  at read time), but the manifest-fingerprint reassessment step — and
  therefore automatic `MANIFEST_CHANGE` review-item enqueuing — is skipped,
  with a printed note.
- A vault-request failure of any kind during `gaps`/`check` is a **warning
  only**: the primary command output and exit code are unaffected.

## Environment variables

| Variable | Purpose |
|---|---|
| `OPENCOMPLAI_VAULT_URL` | Evidence-vault base URL. Required for any control-register feature. |
| `OPENCOMPLAI_RISK_ENGINE_URL` | risk-engine base URL. Required for automatic reassessment after sync. |
| `INTERNAL_SERVICE_TOKEN_SECRET` | Shared secret used to mint signed service-to-service tokens for vault/risk-engine calls. |
| `OPENCOMPLAI_TENANT_ID` | Tenant scope for control derivation and vault requests. Defaults to `oss-default`. |

## CLI examples

See the full [`opencomplai controls`](../cli/controls.md) reference.

```text
$ opencomplai controls status --system-id loan-decision-model
controls: 17 total · 1 satisfied · 15 evidence_missing · 1 evidence_stale · 0 pending_review · 0 waived · 1 stale-by-ttl
```

exits `1` here — attention needed.

## See also

- [Annex IV coverage ledger](annex-iv-coverage.md) — how gaps-derived, wired, and attested Annex IV content relates to controls.
- [Evidence](evidence.md) — the evidence objects controls reference.
