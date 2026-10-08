# Upgrading to 0.9

Release 0.9.0 changes a few behaviours that 0.8 users, CI jobs and API callers rely on; each row below names who is
affected and what to do. If you push to the hosted dashboard, upgrade the CLI only after that dashboard runs 0.9.0.

| Change | Who is affected | What to do |
|---|---|---|
| `opencomplai check --sign` with no signing key exits 2 and writes no artifact; a signing error under `--sign` is exit 2, and `halt approve` follows the same rule | CI jobs that pass `--sign` without a key | Use `--sign-if-available` for the old behaviour plus a warning, or provide a key (see [check](../cli/check.md) and [key management](../security/key-management.md)); the GitHub Actions and GitLab CI connectors already pass it unless `SIGNING_KEY_PRIVATE` is set |
| A manifest with a `systems` key, or one that is a top-level JSON array, is rejected with exit 2 | Anyone who described several systems in one manifest | Write one manifest per system and pass each with `-m` (see [portfolio mode](../cli/portfolio.md)) |
| Satisfying a dashboard control needs an evidence note; an empty or missing note returns 422 | Direct API callers of `POST .../controls/{id}/satisfy` | Send `{"evidence_note": "..."}` in the request body |
| Dossiers are no longer HMAC-signed: with only `LOCAL_SIGNING_KEY_PATH` set a dossier is `unsigned`, and an older `hmac-local` dossier verifies as `invalid` with code `UNSUPPORTED_SIGNATURE` (exit 1) | Anyone who relied on `hmac-local` dossiers | Sign with an Ed25519 key; treat older `hmac-local` dossiers as unverifiable, not as tampered (see [verify](../cli/verify.md)) |
| The dashboard audit log is a per-tenant hash chain behind row-level security, its tables are append-only, and the tenant audit CSV ends with a `# chain_head` line | Database roles that updated or deleted audit rows; readers of the audit CSV | Stop updating or deleting audit rows; skip or read the final `# chain_head` line when parsing the CSV. Events recorded before the update are kept but not chained |
| Dashboard tenant roles are enforced: waive, satisfy and clear are admin-only, assign, due date, system metadata and risk classification need member, and viewers can no longer write or open, reply to or close support tickets | Viewers and members who made those writes | Give users who need those writes the member or admin role |
| The evidence vault `GET /v1/portfolio` row `status` changed from `compliant` to `scan_passed` | Clients that read that value | Match on `scan_passed` |
| `GET /v1/evidence/ledger-history-tips` without parameters answers 413 above 10,000 events; `after_seq` without `limit` is a 422; an older `tools/verify-ledger` cannot check a ledger above the cap | Callers of that endpoint and users of older verify-ledger copies | Page with `limit` (1 to 5000) and `after_seq`, and use the current `tools/verify-ledger` |
| Dashboard ingest rejects a request body over 2 MiB with 413 `VALIDATION_ERROR` | Anyone pushing very large artifacts | Keep each pushed body under 2 MiB |
| `SIGNING_KEY_PRIVATE` is validated as base64; a value with stray characters other than line wraps and a trailing newline raises `SigningKeyError` | Anyone with a malformed key value | Store the key as clean base64 (see [key management](../security/key-management.md)) |
| The `opencomplai-ai` base install no longer pulls `transformers` and `onnxruntime` | Code that relied on them arriving with the base install | Install the `[onnx]` extra for the Python-API ONNX export, or install the packages yourself |
| The Docker Compose stack publishes the Prometheus and Grafana ports on `127.0.0.1` | Anyone who reached either UI from another host | Set `OBSERVABILITY_BIND_ADDR=0.0.0.0` in `infra/compose/.env` and recreate the containers, after reading [Network exposure](../deployment/observability.md#network-exposure) |
| A hosted dashboard older than 0.9.0 answers every artifact from a 0.9.0 CLI with `SCHEMA_VIOLATION`, because its ingest schema is closed | Anyone who runs `opencomplai push` | Upgrade the CLI only after the dashboard you push to runs 0.9.0 |

The full list of changes is in the
[changelog](https://github.com/Opencomplai/opencomplai/blob/main/CHANGELOG.md).
