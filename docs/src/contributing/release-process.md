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
7. **Pushing the tag triggers `.github/workflows/publish-pypi.yml`** — it
   builds the checker widget, builds all four distributions, then publishes
   them to PyPI in the dependency order above via **Trusted Publishing**
   (OIDC; no stored API token) with PEP 740 attestations. Each upload uses
   `skip-existing: true`, so re-pushing a tag for a version already on PyPI
   is a no-op, not an error.
8. **Create a GitHub Release** from the tag with the CHANGELOG section as the body.

---

## Hotfixes

For critical security or correctness fixes on a released version:

1. Branch from the release tag: `git checkout -b hotfix/vX.Y.Z+1 vX.Y.Z`.
2. Apply the minimal fix.
3. Follow the release checklist from step 2.
