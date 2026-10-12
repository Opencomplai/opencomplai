# Hosted dashboard architecture

!!! note "This is the hosted product, not part of the OSS install"
    `dashboard-saas` is the multi-tenant hosted dashboard of the Pro tier. It is a separate
    deployment from everything else in these docs: the open-source packages (`opencomplai-core`,
    `opencomplai-cli`, the SDK) and the Docker Compose stack in [Deployment](../deployment/quickstart.md)
    neither contain it nor depend on it. The local dashboard that ships with the CLI is
    [`opencomplai serve`](../cli/serve.md); see
    [ADR: Local serve vs SaaS](adr-local-serve-vs-saas.md) for why the two are kept apart.

    This page describes how the code is built. It says nothing about any particular live
    deployment. Paths below are relative to the `dashboard-saas/` source tree.

## Product boundary

The dashboard ingests **only signed, allowlisted metadata** produced by OSS installs. It never
receives raw evidence, model artifacts, datasets or PII. Anything that would persist or render a
field outside the pinned allowlist is a scope violation, not a feature gap.

## Components

| Component | Runtime | What it does | Local dev port |
|---|---|---|---|
| `services/ingest-api` | FastAPI | Verifies and persists signed artifacts from OSS installs. The only route by which artifact data enters the database. | 9001 |
| `services/render-api` | FastAPI | Read-only tenant queries (systems, timelines, metrics, dossiers, controls, portfolio, audit view). | 9002 |
| `services/admin-api` | FastAPI | Tenant lifecycle, enrollment, signup, invitations, projects and API keys, RBAC, billing, support, platform-operator actions. | 9003 |
| `services/web` | Next.js 14 (App Router), Auth.js v5 | Tenant-facing UI, sign-in, and the token issuer the other three trust. | 9004 |
| `packages/dashboard_db` | Python | SQLAlchemy models, `schema.sql`, and the session helpers that apply row-level security. | |
| `packages/dashboard_auth` | Python | JWT and JWKS verification shared by the three FastAPI services. | |
| `packages/dashboard_checker` | Python | Vendored copy of the EU AI Act applicability checker engine, kept in sync by a drift check. | |
| `schemas/` | JSON Schema | Per-artifact schemas and the field allowlist, vendored from the OSS release and pinned by commit. Never edited locally. | |

```text
 OSS install                                   Browser
 (opencomplai push)                               |
      | signed envelope + bearer token            v
      v                                    +--------------+
 +------------+                            |     web      |  mints an RS256 JWT per call,
 | ingest-api |                            |  (Next.js)   |  publishes /.well-known/jwks.json
 +------------+                            +--------------+
      |                                       |         |
      |                       bearer JWT      v         v
      |                              +------------+ +-----------+
      |                              | render-api | | admin-api |
      |                              |   (read)   | | (lifecycle|
      |                              +------------+ |  and ops) |
      |                                     |       +-----------+
      v                                     v             v
 +------------------------------------------------------------+
 | Postgres: tenant fence (row-level security) set per request |
 +------------------------------------------------------------+
```

ingest-api, render-api and admin-api each verify the bearer token against the JWKS named by
`OIDC_JWKS_URI`, which is where the web app publishes its keys (ingest-api additionally accepts
project API keys, described below).

Every Python service exposes `GET /health` (liveness) and `GET /ready` (readiness). `/ready`
probes the database and the row-level-security posture on every call, and answers 503 when
either fails: the login role must be neither a superuser nor `BYPASSRLS`, the two application
roles must carry the attributes the session helpers assume, and every tenant table must have
row-level security enabled, forced and policed. Setting `OPENCOMPLAI_REQUIRE_RLS_POSTURE=1`
additionally makes each API refuse to start when that check fails; it is off by default and does
not change what `/ready` answers.

Every API response carries an `x-request-id` header. An inbound value is kept when it is 8 to 64
characters of letters, digits, `.`, `_` or `-`; otherwise one is minted. Error bodies repeat it as
`request_id` next to the unchanged `detail`.

The three Python services do not call the OSS backend services: render-api's open-items summary,
for example, is a plain aggregation over `control_rows`.

## ingest-api: the allowlist and the signed envelope

`POST /v1/ingest/scan-status`, `/v1/ingest/dossier-envelope` and `/v1/ingest/metrics` each accept
one envelope:

```json
{
  "install_id": "opaque id of the OSS install",
  "system_id": "identifier of the AI system",
  "signature": "base64 Ed25519 signature",
  "artifact": { "...": "must match the schema for this endpoint" }
}
```

`tenant_id` is never accepted from the client. A body that sets it is rejected with
`VALIDATION_ERROR`; the tenant is taken from the authenticated principal.

Each request runs this pipeline in order. Any failing step stops it and nothing is persisted.

| Step | Check | On failure |
|---|---|---|
| 1 | Resolve the principal from the bearer token (see [Authentication](#authentication)). | 401, or 429 for a rate-limited project API key |
| 2 | **Body limit.** A body larger than 2 MiB is refused, by its declared length or by what was read, before it is parsed. | 413 `VALIDATION_ERROR` |
| 3 | Envelope shape: required fields present, `artifact` is an object, no client-set `tenant_id`. | 422 `VALIDATION_ERROR` |
| 4 | **Consent gate.** An active `EgressConsent` must exist for this tenant and install. It is checked before any signature work. | 403 `EGRESS_NOT_CONSENTED` |
| 5 | **Allowlist.** The artifact is validated against the vendored JSON Schema for its kind. The schemas set `additionalProperties: false`, so an unknown field fails the request. The dashboard rejects such a payload outright and never strips fields and accepts the remainder. | 422 `SCHEMA_VIOLATION` |
| 6 | **Signature.** Verify the Ed25519 signature against the tenant's registered signing keys (below). | 422 `SIGNATURE_INVALID` |
| 7 | Persist idempotently. On a first write, also record the audit event and evaluate alerts. | 201 on first write, 200 on a duplicate |

Rejections after step 2 write an `INGEST_REJECTED` audit event; acceptance writes `INGEST_ACCEPTED`.

**What is signed.** The signed bytes are the artifact serialised as canonical JSON (Python
`json.dumps` with `sort_keys=True`, the `signature` field excluded) behind a fixed domain-separation
prefix, `opencomplai.sig.v1`, a NUL byte, `scan-status-artifact`, and another NUL byte. The prefix
means a signature made by the same key for another purpose, such as a compliance badge, does not
verify as an artifact signature. The ingest side reimplements the canonicalisation rather than
importing the OSS package, and a parity test fails the build on the first differing byte.

**Which keys count.** A tenant registers one or more public keys (`POST
/v1/admin/tenants/{tenant_id}/signing-keys`, or automatically during `opencomplai dashboard
enroll`, see [CLI: dashboard](../cli/dashboard.md)). Keys can be rotated: a retired key stays on
file so that artifacts signed before its retirement remain verifiable.

**Idempotency.** The primary key of `ingested_artifacts` is `(tenant_id, install_id,
content_hash)`, where the hash is the SHA-256 of the canonical artifact. Re-posting the same
artifact writes nothing and answers 200 with `outcome: "replayed"` (a first write answers 201
with `outcome: "accepted"`), the same `content_hash`, and an `Idempotency-Key` header. The
`signer_key_id` and `signature_verified_at` in that body come from verifying the repeated request,
not from the stored row.

**The allowlist, in two places.** At request time the per-kind schema is the effective allowlist.
`schemas/allowed_fields.json` is a mirror of the egress-proxy's `ALLOWED_FIELDS` in the OSS tree;
a contract test asserts the two are identical, and the egress-leak tests exercise it. The vendored
schemas are pinned in `schemas/PIN.json`, and CI fails if they drift without a recorded re-pin.

**Project API keys.** A bearer token starting `ock_` is a project-scoped API key (for example for a CI
connector). It is looked up by its SHA-256 hash; an unknown, revoked or archived key, or a tenant
that is not active, all produce the same 401 body. The install id comes from the key's project, and
a signature becomes optional: if the envelope has none, the row records that the API key attested
it, and if it has one it is verified exactly as above. Keys are rate limited per key
(`OPENCOMPLAI_INGEST_KEY_RATE_LIMIT`, default 120 per minute) and the limiter fails closed.

After a `scan_status` artifact is accepted, ingest also derives lineage rows and upserts the
optional `controls` block into `control_rows`. Alert rules (`TRAP_DETECTED`, `DOSSIER_FAILURE`,
`CONTROL_REGRESSION`) are evaluated against the stored metadata only.

**Provenance and summaries.** The `scan_status` schema accepts the provenance fields the CLI
stamps on a check (including `rule_set_version`, `cli_version`, `schema_version` and
`manifest_sha256`) and one optional, closed `summaries` block with the keys `oversight`, `agents`,
`qms`, `incidents` and `packs`. The block holds counts, enums, dates and hashes only, with no free
text. After the artifact is stored, ingest projects it: `oversight`, `agents` and `qms` into
`system_summaries` (the newest artifact timestamp wins, so a replayed older push never overwrites
a newer one), `incidents` into an incident table, and `packs` into a pack-issuance register. A failure in the
`system_summaries` or pack projection is logged and never fails the push, and a replay of the same
artifact retries it. Everything shown from `summaries` is what the CLI reported; the dashboard does
not verify it.

## render-api: read-only queries

render-api has no write path. Its routes cover the system list and per-system timeline, metrics,
dossiers, gap report, controls and data flow, plus portfolio, policy drift, pipeline health, an
open-items summary, a tenant audit view and a tenant data export. The artifact queries run inside
`tenant_session` (see [Tenancy](#tenancy-row-level-security)), so row-level security fences them.
They also carry an explicit `tenant_id` predicate, so a regression in a database policy cannot
silently leak those rows, and a test fails CI if one of those query functions loses its
`tenant_id` argument. Routes that return stored artifact JSON pass it through a redaction step
first.

All paths below are under `/v1`. Every route is a `GET` and is scoped to the caller's tenant.

| Path | Returns |
|---|---|
| `/systems` | The tenant's systems, with their latest status and register metadata. |
| `/systems/{system_id}/timeline` | Scan and dossier history for one system. |
| `/systems/{system_id}/changes` | The controls added, removed or moved to another state between the two latest scans that report controls, as the pipeline reported them. |
| `/systems/{system_id}/ruleset-changes` | Whether the rule set has changed since the system's newest scan. |
| `/systems/{system_id}/metrics` | Rates computed over a window of the system's recent scans. |
| `/systems/{system_id}/dossiers` | The system's dossier list. |
| `/systems/{system_id}/dossiers/{bundle_checksum}` | One dossier, by bundle checksum. |
| `/systems/{system_id}/gap-report` | The gap report for a framework the plan includes. |
| `/systems/{system_id}/report-signoff` | The latest sign-off on the system report, the current report hash, and whether a newer scan has arrived since. |
| `/systems/{system_id}/controls` | The system's control rows. |
| `/systems/{system_id}/data-flow` | The data-flow graph derived from reported artifacts. |
| `/systems/{system_id}/oversight` | Human-oversight counts reported by the CLI. |
| `/systems/{system_id}/qms-summary` | Quality-management clause statuses reported by the CLI. |
| `/systems/{system_id}/agents` | Agent counts and coverage reported by the CLI. |
| `/controls/portfolio` | Controls across every system, optionally in priority order. |
| `/portfolio` | Per-system rates over a window of recent scans. |
| `/open-items/summary` | A count of open items. |
| `/review-queue/summary` | A deprecated alias of the open-items summary, served with deprecation headers. |
| `/policy-drift` | Systems whose policy bundle is behind the configured floor or stale. |
| `/pipeline-health` | Whether each system's pipeline is reporting. |
| `/incidents` | The incident register projected from scan summaries. |
| `/audit` | The tenant-facing audit log, paginated and filterable, with the newest chain head. |
| `/export` | A zip of the organisation's data. Organisation admins only; each export is audited. |

The three CLI-reported routes (`oversight`, `qms-summary`, `agents`) return what the CLI said and
mark it as not verified by the dashboard.

## admin-api: lifecycle and operations

admin-api is where tenant, membership and operational state is written. Its route groups:

| Group | Purpose |
|---|---|
| Tenants (`/v1/admin/tenants/...`) | Create, suspend, close (soft-delete); add users; register and retire signing keys; grant and revoke consent. Closing an organisation stops ingest and revokes its active API keys. |
| Enrollment (`/v1/admin/enroll`, `/v1/admin/withdraw`) | Exchange a single-use bootstrap token for a registered signing key and an `EgressConsent`; withdraw consent. |
| Signup and invitations | Self-serve organisation creation, member invitations (a pending one can be re-sent), role changes, and leaving an organisation (the last administrator cannot leave). |
| Projects and API keys | Projects within a tenant and the `ock_` keys that ingest accepts. |
| RBAC | Roles `admin`, `policy_manager`, `release_approver`, `reviewer`, `viewer`, scoped by org, project or system, with time-boxed break-glass elevation. |
| Systems | Self-declared system metadata, risk assessments, control assignment, due dates, waivers, evidence-noted satisfaction, and links to upstream systems or suppliers. |
| Register | Download the AI register as CSV and bulk-import it, with a dry-run preview. An import is all-or-nothing. |
| Report sign-off | An organisation admin signs a system report with a typed statement, bound to a scan and to a hash of the rendered report. |
| Share links | Revocable links to one system's report, and the register of deployer packs issued. Only the SHA-256 of a link token is stored. |
| Billing | A provider seam: a local simulator by default, with a Stripe driver that stays dormant unless `STRIPE_SECRET_KEY` is set, and a webhook whose signature is verified fail-closed. |
| Support | Tenant support tickets and messages. |
| Platform (`/v1/platform/...`) | Operator-only cross-tenant actions: listing, plan override, suspend and reinstate, restoring or purging a closed organisation, read-only tenant view, audit-chain verification, operator management, user erasure and retention purge. Each write requires a reason and writes an audit event; erasure and purge are dry runs unless asked otherwise. |
| Checker | An anonymous, rate-limited evaluate endpoint backed by the vendored checker. |

Most routes need an RBAC permission on the target tenant. A caller with no role assignment there
has no permissions and is denied. Projects, API keys, billing checkout and portal, invitations and
member changes need the `manage_tenants` permission, which only the RBAC `admin` role holds.

Writes that act on a tenant's own data are also gated by the caller's **tenant role** (`admin`,
`member` or `viewer`, read from `tenant_users` on each request). A viewer cannot write. Satisfying,
waiving and clearing a control, report sign-off and share links need `admin`; control assignment,
due dates, system metadata, risk classification, support tickets and register import need
`member`. A denial uses one uniform 403 that does not say which check failed.

## web: UI and token issuer

The web app renders the tenant UI from Server Components and route handlers. It calls render-api
and admin-api server-side with a freshly minted token, and does not cache those responses
(`cache: "no-store"`), so a stale compliance figure is never served. It also reads Postgres
directly for the few queries that sit on the far side of the tenant fence: which tenants a user
belongs to, and the read-only organisation and platform views. Anything that changes tenant state
goes through admin-api, which holds the RBAC engine and the audit sink.

**Public, signed-out routes.** A few routes under `services/web/src/app/(public)/` need no account:

| Route | What it does |
|---|---|
| `/s/<token>` | Opens a report share link and shows one system's report. A malformed, unknown, expired or revoked link, or one of a closed organisation, gets the same 404. The route is rate limited per IP and records each view as an audit event. The page leaves out emails, owners, signing keys and waiver text. |
| `/verify/pack/<sha256>` | Looks up a deployer-pack hash and confirms that it was issued. It shows the pack kind and the issue date only: no tenant, system or signing key. |
| `/verify/attestation` | Checks a signed agent attestation against the public keys registered with the dashboard. No account is needed and nothing is stored. A valid result does not identify the signer. |

## Tenancy: row-level security

The database, not the application, is the tenant fence. `schema.sql` is the source of truth.

- Every tenant-scoped table has a `tenant_id` column, `ENABLE ROW LEVEL SECURITY`, **and**
  `FORCE ROW LEVEL SECURITY`, with a policy of the form
  `USING (tenant_id = current_setting('app.tenant_id', true))`. `FORCE` makes the policy apply to
  the table owner too.
- `tenant_session(factory, tenant_id)` opens a session, runs `SET LOCAL ROLE dashboard_app` (a
  `NOSUPERUSER NOLOGIN` role that RLS applies to), then
  `SELECT set_config('app.tenant_id', :tid, true)`. `SET LOCAL` and the `true` make the role and
  the tenant setting local to the transaction, so neither carries over to the next request on a
  pooled connection. As a second guard, the connection pool rolls back and runs `RESET ROLE` when
  a connection is returned. An empty tenant id is refused.
- `privileged_session(factory)` runs `SET LOCAL ROLE dashboard_admin` (a `BYPASSRLS` role) with no
  tenant set. It exists for the deliberately cross-tenant paths: creating a tenant, resolving an API key
  before any tenant is known, the Stripe webhook, platform-operator actions and the audit export.
- Tables fall into three tiers. Tenant-policy tables, `audit_events` among them, carry the policy
  above. An identity and catalog plane (`dashboard_auth_users`, verification tokens, `plans`,
  rate-limit counters) has no RLS because no tenant exists yet when it is read, or there is nothing
  tenant-specific to isolate. An admin plane (`platform_admins`, `rbac_role_assignments`, `rbac_break_glass_elevations`,
  `bootstrap_tokens`) enables and forces RLS with **no policy at all**, which denies `dashboard_app`
  everything and leaves the tables readable only through `dashboard_admin`.
- `audit_events` has row-level security enabled and forced like the tenant tables, so tenant audit
  reads go through the fence. It is append-only: update, delete and truncate are rejected by
  trigger and revoked from `dashboard_app` and `dashboard_admin`. Each tenant's rows form a
  SHA-256 **hash chain**: a database trigger numbers each new row, links it to the previous row's
  hash and computes its own, serialised per tenant. A platform operator can ask the database to
  walk a tenant's chain and report the first row that does not verify, and the tenant audit
  response carries the newest chain head. Events recorded before the chain was added are kept but
  are not chained, and verification skips them. Rows record who acted as `actor_id` and
  `actor_kind`.
- The unit tests run on SQLite, where the role and setting calls are skipped. The Postgres
  integration test `tests/test_rls_postgres.py` is the authoritative check of the fence.

## Authentication

Two credentials, in one direction. The web app is its own identity provider; nothing is delegated
to a hosted one.

1. **Browser to web.** Auth.js v5 signs a user in with an emailed **magic link** sent through
   Brevo's transactional API. No password is collected, transmitted or stored. The session is a JWT
   in an encrypted, httpOnly cookie that lasts at most 8 hours. The Postgres adapter holds only two
   tables, the users and the single-use verification tokens (consumed by an atomic
   `DELETE ... RETURNING`). If email or the database is not configured, `/login` says which
   variables are missing and shows no form; there is no password fallback.
2. **Web to services.** For each outbound call the web app mints a short-lived **RS256 JWT**
   (default lifetime 600 seconds, clamped to 300 to 900). It carries `sub` (the Auth.js user id)
   and a tenant claim whose name comes from `AUTH_JWT_TENANT_CLAIM`. The token is minted inside
   Server Components and route handlers and never reaches the browser. The Python services never
   see the session cookie and could not verify it.
3. **JWKS.** The web app publishes its **public** keys at `/.well-known/jwks.json`. The current and
   the previous `kid` are both published, so a key rotation does not invalidate tokens already
   minted; only the current private key is ever deployed. With no key configured the route answers
   503 `jwks_not_configured` rather than an empty key set.
4. **Services verify.** `dashboard_auth` fetches the JWKS from `OIDC_JWKS_URI`, pins RS256, and
   enforces `exp`, `nbf`, `iss` and `aud`. The tenant is read from the claim named by
   `OIDC_TENANT_CLAIM`. `OIDC_ISSUER`, `OIDC_AUDIENCE` and `OIDC_TENANT_CLAIM` have no defaults and
   are required whenever `OIDC_JWKS_URI` is set; the service refuses to start otherwise. These are
   the same rules as the OSS gateway's OIDC mode, described in
   [Authentication Configuration](../deployment/authentication.md).
5. **The tenant is never asserted by the browser.** The web app resolves it from `tenant_users` on
   every request, not from the session, so removing a membership takes effect on the next page
   load. That one lookup is cross-tenant by nature and runs under `SET LOCAL ROLE dashboard_admin`
   for a single transaction.

The same JWT path serves platform operators: the token carries a `platform_admin` claim, which
admin-api re-checks against the `platform_admins` table instead of trusting the claim alone.

`OPENCOMPLAI_AUTH_DISABLED=1` is a local-development bypass in which the services trust an
`X-Tenant-Id` header. The services refuse to start with it set unless `OPENCOMPLAI_DEV=1` is set or
the database is SQLite or loopback Postgres with `VERCEL_ENV` unset.

## See also

- [ADR: Local serve vs SaaS](adr-local-serve-vs-saas.md): why the local dashboard and the hosted
  product stay separate.
- [CLI: dashboard](../cli/dashboard.md): enrolling an OSS install, which establishes the consent
  and the signing key the ingest pipeline checks.
- [Authentication Configuration](../deployment/authentication.md): the OIDC rules these services
  mirror.
- [System Design](system-design.md): the OSS service stack, which is a different deployment.
