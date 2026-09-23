# Exit codes

Opencomplai uses fixed, contractual exit codes so CI pipelines can reliably gate merges and deployments.

| Code | Constant | When it happens |
|---:|---|---|
| `0` | `PASS` | All critical controls passed. |
| `1` | `CONTROL_FAIL` | One or more critical controls failed (e.g. an Annex III high-risk use case, or a failed pipeline evaluator). |
| `2` | `VALIDATION_FAIL` | Input or manifest validation failed (e.g., missing or invalid `system-manifest.json`). |
| `3` | `POLICY_BLOCK` | A prohibited (Article 5) practice was detected in the declared purpose, e.g. `social scoring`, or the manifest's checker verdict is `prohibited_practice`. |
| `4` | `TRAP_DETECTED` | Article 25 substantial-modification trap: the change makes you a provider. Raised locally by `--change-context model_retrain`, `purpose_change` or `capability_extension`, and by the risk engine in service-backed mode. |

## Typical CI usage

```yaml
- name: Compliance check
  run: opencomplai check
  # Step fails automatically on exit code 1, 2, 3, or 4.
```

## Remediation

| Exit code | Action |
|---|---|
| `1` | Review failed rules in the human output. Fix the compliance gap, then re-run. |
| `2` | Run `opencomplai init` first, or check that `system-manifest.json` is valid. |
| `3` | The system as declared is a prohibited practice under Article 5. Review the intended purpose with your compliance team; it cannot be placed on the EU market as described. |
| `4` | The system is halted pending review (see below). Complete the provider obligations for the modified system, then `approve` and `resume`. |

## Control register (`opencomplai controls`)

`opencomplai controls status` mirrors the same exit-code convention for the persistent control register (requires `OPENCOMPLAI_VAULT_URL`):

| Exit code | When it happens |
|---:|---|
| `0` | Every control is satisfied or waived, and none are stale by TTL. |
| `1` | A control is `evidence_missing` (unless `--no-fail-on-missing`), `evidence_stale`, `pending_review`, or stale by TTL. |
| `2` | `OPENCOMPLAI_VAULT_URL` is not set, or an input (control id, file path) was invalid. |
| `3` | The evidence-vault request failed (network/service error). |

`controls list` and `controls assign`/`attach-evidence` always exit `0` on success — only `status` gates CI.

## Halt / resume gate (`opencomplai check`, `opencomplai docs generate`)

When `check` detects a trap (`TRAP_DETECTED`), or an unresolved HIGH-risk corroboration gap (HIGH risk class plus a failed `--scan --fail-on ...` gate), the system is persisted as `HALTED_PENDING_REVIEW`. While halted, `opencomplai docs generate` for that `system_id` refuses with exit `4` and no dossier is written — there is no `--force` bypass. Resume with `opencomplai approve --system-id ... --approver ...` to mint a signed approval token, then `opencomplai resume --system-id ... --approval-token ...`; an invalid or mismatched token exits `2` and leaves the system halted.

## Fail-closed dossier gate (`opencomplai docs generate`)

`docs generate` also exits `2` (`VALIDATION_FAIL`) — separately from the halt gate above — when the generated Annex IV dossier itself fails schema validation (a HIGH-risk dossier missing required Section 2-9 content or provider attestations). The dossier is still written to disk (or persisted server-side by the doc-generator service, which returns HTTP `422` for the same case) so an auditor can see what failed; only the exit code communicates failure. Pass `--allow-incomplete` (CLI) or `allow_incomplete: true` (service request body) to restore the old always-succeed behaviour, e.g. for a CI pipeline that only wants the dossier artifact and gates completeness separately. See [`docs generate`](docs-generate.md#fail-closed-dossier-gate).
