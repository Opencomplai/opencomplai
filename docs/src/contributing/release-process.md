# Release Process

Opencomplai follows [Semantic Versioning](https://semver.org/) (`MAJOR.MINOR.PATCH`).
Four Python packages ship from this repo, all published to PyPI:
`opencomplai-core`, `opencomplai-cli`, `opencomplai-ai`, and the `opencomplai`
meta-package (the SDK). To find the version currently released, check the
`version` field in `packages/core/pyproject.toml` (the other three packages
track it — see below), the PyPI badge in the repo README, or run
`opencomplai --version`. Don't trust a version number written into this page
as a fact — packages move fast enough that it would go stale.

---

## Version policy

| Package | Versioning |
|---|---|
| `opencomplai-core` | Semver; breaking model or rule API changes bump MAJOR |
| `opencomplai-cli` | Semver; new commands or changed exit codes bump MINOR |
| `opencomplai-ai` | Semver; follows `core` |
| `opencomplai` (SDK meta-package) | Semver; follows `core` and `cli` |
| Gateway API | Path-prefix versioning (`/v1/`, `/v2/`); parallel for ≥ 90 days |

All four Python packages move together — same version number across all four
`pyproject.toml` files in a given release. The gateway API versions
independently of the Python packages.

---

## Build and publish order

The four packages have a dependency chain, so they are built and published
in this order (both locally and in CI):

1. **`opencomplai-core`** — no local dependencies.
2. **`opencomplai-cli`** — depends on `opencomplai-core`.
3. **`opencomplai-ai`** — depends on `opencomplai-core` only, independent of `cli`.
4. **`opencomplai`** (SDK meta-package) — depends on both `opencomplai-core`
   and `opencomplai-cli`, so it is always built and published last.

### Checker widget build prerequisite

Before `opencomplai-cli` is built, the docs checker widget must be built:

```
cd docs/checker-widget && npm ci && npm run build
```

This generates `packages/cli/src/opencomplai_cli/data/checker-local.html`, a
git-ignored asset that `packages/cli/pyproject.toml` force-includes into the
wheel. Skip this step and the `opencomplai-cli` build fails with "Forced
include not found." `.github/workflows/publish-pypi.yml` runs this build
automatically before building any of the four distributions, so a tag-push
release never needs it done by hand.

---

## Release checklist

1. **Create a release branch** from `main`: `git checkout -b release/vX.Y.Z`.
2. **Bump `version`** to the same new value in all four package manifests:
   - `packages/core/pyproject.toml`
   - `packages/cli/pyproject.toml`
   - `packages/ai/pyproject.toml`
   - `packages/sdk-python/pyproject.toml`
3. **Update `CHANGELOG.md`** — move items from `Unreleased` to the new version heading.
4. **Run the full test suite**: `uv run pytest packages/` for the four
   Python packages, plus `cd services/gateway-api && pnpm test` for the
   gateway API.
5. **Open a release PR** targeting `main`, get it reviewed, and merge it.
6. **Tag the merge commit** `vX.Y.Z` and push the tag.
7. **Pushing the tag triggers `.github/workflows/publish-pypi.yml`** — its
   `build` job first checks the tag against the four manifest versions and
   fails on any mismatch, builds the checker widget and all four
   distributions, runs the wheel smoke test and generates a CycloneDX SBOM
   per package (kept as a workflow-run artifact). Only then does the
   `publish` job upload the tested distributions to PyPI in the dependency
   order above via **Trusted Publishing** (OIDC; no stored API token) with
   PEP 740 attestations. Each upload uses `skip-existing: true`, so
   re-pushing a tag for a version already on PyPI is a no-op, not an error.
   A manual `workflow_dispatch` run is a dry run: it builds, smoke tests
   and produces SBOMs, and publishes nothing.
8. **Create a GitHub Release** from the tag with the CHANGELOG section as the body.

---

## Homebrew tap and signing secret

Both operations below are founder-only. Run them by hand on the founder's machine after a release is on PyPI.
Nothing in the release tag workflow creates a repository or a secret.

**Homebrew tap** (run the steps in this order; replace `<version>` with the released version)

1. Confirm the new version's sdist is on PyPI: open `https://pypi.org/project/opencomplai/<version>/#files`.
2. Create the GitHub repository `Opencomplai/homebrew-tap`. The name is a founder choice and is unverified, as noted in `packaging/homebrew/README.md`.
3. In a checkout of the release tag, run `bash scripts/homebrew-release.sh <version>`. It reads the sdist sha256 from the PyPI JSON, downloads the sdist and checks that its bytes match that digest, then patches the `url` and `sha256` in `packaging/homebrew/opencomplai.rb`. It refuses a placeholder or all-zero digest and a checksum mismatch, and it patches the formula once the index, digest and download checks pass; the lint step runs after the patch and a failure leaves the patched file for you to review. Exit code 0 means pass, 1 means a named step failed, 2 means bad usage.
4. Commit the patched formula on its own, a commit that changes only `packaging/homebrew/opencomplai.rb`. Then copy that file to `Formula/opencomplai.rb` in the tap repository.
5. In the tap checkout, run `brew update-python-resources Formula/opencomplai.rb`, then `brew install --build-from-source Opencomplai/tap/opencomplai` and `brew test Opencomplai/tap/opencomplai`.
6. Run `brew style` and `brew audit --strict --new Opencomplai/tap/opencomplai`.
7. Push the tap repository with `git push`.

**What flips planned to live**: only after step 7 is pushed and `brew install Opencomplai/tap/opencomplai` works from a clean machine, edit the "Homebrew (planned)" block in `docs/src/getting-started/installation.md` and the matching assertion in `packages/cli/tests/test_homebrew_formula.py` in one commit. Until then the installation page stays "planned".

**Signing secret** (independent of the tap, and may be done at any time)

Run `gh auth login` yourself first. Then run `bash scripts/signing-secret.sh OPENCOMPLAI_SIGNING_KEY <owner>/<repo>`, where `<owner>/<repo>` is the repository that holds the release workflow. The script generates an Ed25519 key in memory and pipes it straight to `gh secret set`. The private key is never printed and never written to a file. The script prints only the public key, so publish that public key for verifiers. It refuses to replace an existing secret unless you pass `--replace`, because a replacement changes the key that every earlier signature was made with.

For how the secret is used in CI, see [Attach the artifact to a release](../guides/ci-recipes.md#attach-the-artifact-to-a-release). For key handling, see [Key management](../security/key-management.md).

**Order of steps**

1. Release on PyPI through the tag workflow.
2. Create the tap repository.
3. Run `scripts/homebrew-release.sh <version>`, then push the tap.
4. Flip the installation page to live after `brew install` works from a clean machine.
5. Create the signing secret with `scripts/signing-secret.sh` (independent of the tap).

---

## Hotfixes

For critical security or correctness fixes on a released version:

1. Branch from the release tag: `git checkout -b hotfix/vX.Y.Z+1 vX.Y.Z`.
2. Apply the minimal fix.
3. Follow the release checklist from step 2.
