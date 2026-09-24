# Deployment Journey

The complete path from a fresh install to a CI-gated, dashboard-reporting,
pre-commit-enforced deployment — one canonical sequence, so you don't have to
piece it together from separate guides. Each step links to the deeper
reference doc for that topic.

## 1. Install

```bash
pip install opencomplai
```

This installs the CLI, core rule engine, and SDK with a stable API contract (see
[CHANGELOG](https://github.com/Opencomplai/opencomplai/blob/main/CHANGELOG.md) for
exit-code and artifact-schema guarantees).

Contributing from a checkout instead of PyPI? See
[Installation → Install from source](installation.md#install-from-source) — the
`core`, `cli`, and `sdk-python` packages must be installed together in one command.
If you're changing anything under `docs/checker-widget/`, also regenerate the
committed offline-checker bundle — see
[CONTRIBUTING.md](https://github.com/Opencomplai/opencomplai/blob/main/CONTRIBUTING.md#4-development-setup).

## 2. Initialise and check

```bash
opencomplai init --system-id my-model --intended-purpose "customer support chatbot"
opencomplai check
```

`init` creates `system-manifest.json` in the current directory and a signing
keypair under `~/.opencomplai/` on first run. `check` classifies the system
against the EU AI Act, prints a `PASS` / `CONTROL_FAIL` / `POLICY_BLOCK`
verdict, and writes `compliance-artifact.json`. See
[Quick Start](quick-start.md) for the full output of each command, the other
compliance outcomes, and the [exit-code contract](../cli/exit-codes.md).

## 3. Gate CI on the result

Add the same two commands to your pipeline. Any CI platform works the same
way — install the CLI, then let `check`'s exit code fail the job:

```yaml
- name: Opencomplai compliance check
  run: |
    pip install opencomplai
    opencomplai init --system-id "${{ env.MODEL_NAME }}" --intended-purpose "${{ env.USE_CASE }}"
    opencomplai check --scan-mode ci
```

A non-zero exit fails the step automatically. See
[First Project](first-project.md) for a full worked GitHub Actions example
(including uploading `compliance-artifact.json` as a build artifact), and
[CI integration](../guides/ci-integration.md) for ready-to-paste GitHub
Actions / GitLab CI snippets that also push results to the dashboard.

## 4. Optional: push results to the dashboard

To report scan results to the Premium Dashboard instead of (or alongside)
gating CI locally, sign the artifact and push it:

```bash
opencomplai check --sign
opencomplai push
```

`push` reads `OPENCOMPLAI_API_KEY` and `OPENCOMPLAI_DASHBOARD_URL` from the
environment — mint the key on the dashboard's `/connect` page (Projects →
your project → Connect), which also generates the matching CI snippets. See
[CI integration](../guides/ci-integration.md) for the full connector setup.

## 5. Enforce locally with pre-commit

Add Opencomplai's hooks to your own `.pre-commit-config.yaml` so the quick
scan (or the full gate, once you have a manifest) runs on every commit:

```yaml
repos:
  - repo: https://github.com/Opencomplai/opencomplai
    rev: v0.8.0
    hooks:
      - id: opencomplai-quick-scan   # discovery only, never fails the commit
      # - id: opencomplai-check      # full EU AI Act gate — requires system-manifest.json
```

See [Pre-commit integration](../guides/pre-commit.md) for what each hook
runs and how to verify it in your own environment.

## 6. Self-hosted: full Docker Compose stack

For the full platform — Evidence Vault, Documentation Generator, and
service-backed workflows including the `TRAP_DETECTED` substantial-modification
check — run the reference Docker Compose stack instead of the local CLI engine:

```bash
git clone https://github.com/Opencomplai/opencomplai
cd opencomplai
cp infra/compose/.env.example infra/compose/.env
docker compose -f infra/compose/docker-compose.yml up --build -d
```

Set `POSTGRES_PASSWORD` in `infra/compose/.env` before starting — the stack
refuses to start without it. See
[Deployment Quickstart](../deployment/quickstart.md) for migrations, service
ports, health checks, and air-gap mode.

## Next steps

- CLI reference: [check](../cli/check.md) · [init](../cli/init.md) · [exit codes](../cli/exit-codes.md)
- Extending rules: [Adding Rules](../contributing/adding-rules.md)
- Not sure which EU AI Act obligations apply? [EU AI Act Checker](eu-ai-act-checker.md)
