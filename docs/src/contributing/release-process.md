# Release Process

Opencomplai follows [Semantic Versioning](https://semver.org/) (`MAJOR.MINOR.PATCH`). The current version is `0.1.0-dev` (pre-release). This page documents how releases work once v0.1 ships.

---

## Version policy

| Component | Versioning |
|---|---|
| `opencomplai-core` | Semver; breaking model or rule API changes bump MAJOR |
| `opencomplai-cli` | Semver; new commands or changed exit codes bump MINOR |
| `opencomplai` (SDK) | Semver; follows `core` version |
| Gateway API | Path-prefix versioning (`/v1/`, `/v2/`); parallel for ≥ 90 days |

All three Python packages move together (same version number per release). The gateway API versions independently.

---

## Release checklist

1. **Create a release branch** from `main`: `git checkout -b release/v0.x.y`.
2. **Update versions** in:
   - `packages/core/pyproject.toml`
   - `packages/cli/pyproject.toml`
   - `packages/sdk-python/pyproject.toml`
3. **Update `CHANGELOG.md`** — move items from `Unreleased` to the new version heading.
4. **Run the full test suite**: `uv run pytest packages/ && cd services/gateway-api && pnpm test`.
5. **Open a release PR** targeting `main`. Require two maintainer approvals.
6. **Tag and merge**: after merge, tag `v0.x.y` on the merge commit.
7. **Publish to PyPI** (CI handles this on tag push via `ci-python.yml`).
8. **Create a GitHub Release** from the tag with the CHANGELOG section as the body.

---

## Hotfixes

For critical security or correctness fixes on a released version:

1. Branch from the release tag: `git checkout -b hotfix/v0.x.y+1 v0.x.y`.
2. Apply the minimal fix.
3. Follow the release checklist from step 2.

---

## Pre-release (current state)

Until v0.1 ships:

- Packages are versioned `0.1.0-dev` and **not published to PyPI**.
- Install from source: `uv pip install -e packages/sdk-python`.
- The `CHANGELOG.md` `Unreleased` section tracks changes.
- The README badge reads `pre-alpha` to reflect this status.
