# Upgrading to 0.9

Release 0.9.0 changes a few behaviours that 0.8 users, CI jobs and API callers rely on; each row below names who is
affected and what to do.

| Change | Who is affected | What to do |
|---|---|---|
| `opencomplai check --sign` with no signing key exits 2 and writes no artifact; a signing error under `--sign` is exit 2, and `halt approve` follows the same rule | CI jobs that pass `--sign` without a key | Use `--sign-if-available` for the old behaviour plus a warning, or provide a key (see [check](../cli/check.md) and [key management](../security/key-management.md)); the GitHub Actions and GitLab CI connectors already pass it unless `SIGNING_KEY_PRIVATE` is set |
| A manifest with a `systems` key, or one that is a top-level JSON array, is rejected with exit 2 | Anyone who described several systems in one manifest | Write one manifest per system and pass each with `-m` (see [portfolio mode](../cli/portfolio.md)) |
| Dossiers are no longer HMAC-signed: with only `LOCAL_SIGNING_KEY_PATH` set a dossier is `unsigned`, and an older `hmac-local` dossier verifies as `invalid` with code `UNSUPPORTED_SIGNATURE` (exit 1) | Anyone who relied on `hmac-local` dossiers | Sign with an Ed25519 key; treat older `hmac-local` dossiers as unverifiable, not as tampered (see [verify](../cli/verify.md)) |
| The evidence vault `GET /v1/portfolio` row `status` changed from `compliant` to `scan_passed` | Clients that read that value | Match on `scan_passed` |
| `GET /v1/evidence/ledger-history-tips` without parameters answers 413 above 10,000 events; `after_seq` without `limit` is a 422; an older `tools/verify-ledger` cannot check a ledger above the cap | Callers of that endpoint and users of older verify-ledger copies | Page with `limit` (1 to 5000) and `after_seq`, and use the current `tools/verify-ledger` |
| `SIGNING_KEY_PRIVATE` is validated as base64; a value with stray characters other than line wraps and a trailing newline raises `SigningKeyError` | Anyone with a malformed key value | Store the key as clean base64 (see [key management](../security/key-management.md)) |
| The `opencomplai-ai` base install no longer pulls `transformers` and `onnxruntime` | Code that relied on them arriving with the base install | Install the `[onnx]` extra for the Python-API ONNX export, or install the packages yourself |
| The Docker Compose stack publishes the Prometheus and Grafana ports on `127.0.0.1` | Anyone who reached either UI from another host | Set `OBSERVABILITY_BIND_ADDR=0.0.0.0` in `infra/compose/.env` and recreate the containers, after reading [Network exposure](../deployment/observability.md#network-exposure) |

The full list of changes is in the
[changelog](https://github.com/Opencomplai/opencomplai/blob/main/CHANGELOG.md).
