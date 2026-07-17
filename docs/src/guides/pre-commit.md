# Pre-commit integration

Opencomplai ships two [pre-commit](https://pre-commit.com/) hook definitions in
`.pre-commit-hooks.yaml` at the repo root, so a consuming project can reference them
directly instead of hand-writing the CLI invocation.

!!! warning "Verify this in your own environment before relying on it in CI"
    This hook definition has been reviewed and its `entry` command manually confirmed
    to run correctly, but the literal `pre-commit run ... --all-files` acceptance test
    (cloning this repo as a `pre-commit` source at a real tag/commit) has not yet been
    run end-to-end against a published release. Run the verification steps below in a
    scratch repo before depending on this in a production pre-commit config.

## Available hooks

| Hook ID | What it runs | Gates the commit? |
|---|---|---|
| `opencomplai-quick-scan` | `opencomplai scan --quick --repo-root .` | **No.** Discovery-only, always exits `0`, no manifest required. |
| `opencomplai-check` | `opencomplai check` | **Yes.** Full EU AI Act compliance gate — fails the commit on `CONTROL_FAIL`, `VALIDATION_FAIL`, `POLICY_BLOCK`, or `TRAP_DETECTED`. Requires `opencomplai init` to have been run first (a `system-manifest.json` must exist). |

## Consumer-side configuration

Add to your own `.pre-commit-config.yaml`:

```yaml
repos:
  - repo: https://github.com/Opencomplai/opencomplai
    rev: <tag/sha>
    hooks:
      - id: opencomplai-quick-scan
      # - id: opencomplai-check   # requires system-manifest.json — see Quick Start
```

Replace `<tag/sha>` with a real released tag (e.g. `v0.1.2`) or commit SHA once one
exists — `pre-commit` clones the repo at that exact revision to run the hook.

Start with `opencomplai-quick-scan` if you don't yet have a manifest — it can never
break a commit. Add `opencomplai-check` once you've run
[`opencomplai init`](../cli/init.md) and want pre-commit to enforce the full compliance
gate locally, before code reaches CI.

## Verifying the hook works in your environment

From a separate scratch repository:

=== "macOS / Linux"
    ```bash
    cat > .pre-commit-config.yaml << 'EOF'
    repos:
      - repo: https://github.com/Opencomplai/opencomplai
        rev: <the commit sha or a new tag>
        hooks:
          - id: opencomplai-quick-scan
    EOF
    pre-commit run opencomplai-quick-scan --all-files
    ```

=== "Windows (PowerShell)"
    ```powershell
    @'
    repos:
      - repo: https://github.com/Opencomplai/opencomplai
        rev: <the commit sha or a new tag>
        hooks:
          - id: opencomplai-quick-scan
    '@ | Set-Content -Path .pre-commit-config.yaml -Encoding utf8
    pre-commit run opencomplai-quick-scan --all-files
    ```

A successful run prints the quick-scan's discovery output and exits `0`.

## How the hooks are defined

Both hooks declare `language: python` with `additional_dependencies: ["opencomplai-cli"]`
— `pre-commit` creates an isolated environment and installs the CLI package into it, so
consumers don't need `opencomplai` pre-installed globally. Both set `pass_filenames:
false` and `always_run: true`, since compliance scanning operates on the whole repo
rather than per-changed-file.
