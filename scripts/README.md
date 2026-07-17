# OSS Publish Scripts

Tooling for syncing the private **opencomplai-enterprise** repo to the public
**opencomplai** (AGPL) repo.

> Model: **Camp 2 — private is primary, OSS is a derived artifact.** All
> development happens in the enterprise repo. The public repo is rebuilt from a
> clean projection of the enterprise tree with all private content stripped.

The sync is **manual and human-reviewed** — there is no automated CI push, and
**the scripts never commit or push.** They only transfer/update files in your
public-repo working tree. A developer assembles the tree, verifies it, reads the
change report, reviews the diff in their editor, and pushes only after approving.

---

## TL;DR — the one command to run

```bash
# From the enterprise repo root. Arg = your local clone of the PUBLIC repo.
bash scripts/sync-oss.sh ~/repos/opencomplai-public
```

That single command:

1. **Shows what changed** since the last sync (commit-hash aware — see below).
2. **Assembles** a clean projection of enterprise `HEAD` into the public clone.
3. **Verifies** it (hard gate — nonzero exit means *do not push*).
4. **Records** the synced commit so the next run can show the next delta.

It does **not** commit and does **not** push. When it passes it prints the exact
`git add / commit / push` commands for you to run manually after reviewing.

> **Windows:** run these in **Git Bash** or **WSL** (they are bash scripts).

---

## What "commit-hash aware" means (the enhancement)

Every sync still re-projects the **entire** enterprise tree — that is a
deliberate safety choice (see [Why not transfer only the changed files?](#why-not-transfer-only-the-changed-files)).
What's new is that the sync now **tells you exactly which files changed since the
last sync**, so you review a focused, known set instead of eyeballing a full diff
blind.

How it tracks this:

- After a successful sync, the enterprise commit SHA is written to a **gitignored
  marker** `.oss-sync-state` at the enterprise repo root.
- On the next run, `sync-report.sh` diffs `git diff --name-status <marker>..HEAD`
  and prints the changed files, split into:
  - **WILL appear in the public sync** (public paths), and
  - **STRIPPED as private** (denylisted paths — no public effect).
- It also lists the commits in that range.

The marker is **advisory** — it only sets the report's baseline. It is **never**
used to decide which files to transfer. So a stale, missing, or wrong marker can
make the *report* inaccurate but can **never** cause a leak: the transfer is
always a full, fully-verified re-projection of `HEAD`.

### Provenance (recover the baseline anywhere)

The marker is local and gitignored (it must never leak the internal SHA). To make
the baseline recoverable on any machine, the wrapper prints a commit message with
an `OSS-Synced-From: <sha>` trailer. If you commit with it, the baseline lives in
public git history and `sync-report.sh` will fall back to reading it via
`git -C <public> log --grep OSS-Synced-From` when the local marker is gone.

---

## Scripts

| File | Role |
|---|---|
| `oss-config.sh` | **Single source of truth** — denylist (private dirs/files/globs), secret patterns, size limit, marker/trailer names, and the `oss_is_private` matcher. Edit here when adding a new private path. Not executable; sourced by the others. |
| `assemble.sh` | Exports committed tree (`git archive HEAD`) into an output dir and strips private content. Full re-projection. |
| `verify-oss.sh` | Hard gate. Asserts the output is clean. Nonzero exit = do not push. |
| `sync-report.sh` | **Read-only, advisory.** Prints what changed since the last synced commit (published vs stripped). Transfers nothing. |
| `sync-oss.sh` | The command you run: report → assemble → verify → record marker. Never commits/pushes. |

To add or remove a private path, edit **`oss-config.sh` only** — the other
scripts source it, so they never drift apart.

### Key safety property

`assemble.sh` exports **only committed, git-tracked files** via `git archive HEAD`.
It never copies the raw working tree, so untracked/gitignored files
(`__pycache__/`, `node_modules/`, stray `.env`/`*.key`, local data dumps,
including the `.oss-sync-state` marker itself) cannot leak. It also refuses to
run on a dirty working tree.

---

## Why not transfer only the changed files?

The intuitive optimization — "only copy the files in the diff" — was reviewed and
**rejected**. Full re-projection keeps the public tree a **pure function of
enterprise `HEAD`**, which is the property that prevents leaks. A delta copier
loses that and opens silent failure modes:

- **Denylist changes don't self-heal.** If you add a new private path *after* a
  file already shipped, that unchanged file never appears in a diff, so a delta
  copier would never remove it. Only a full re-projection drops it.
- **Renames can strand public files.** A move from a public path to a private one
  is a delete the public tree must reflect; a naive delta keyed on the new
  (private) path can skip it, leaving the old public file behind. (`sync-report.sh`
  uses `--no-renames` so moves always show as delete+add.)
- **Idempotency is lost.** One missed deletion becomes a permanent, invisible
  leak. Full projection is convergent by construction.
- **Upstream edits stay visible.** If a community PR edited a shared file, full
  re-projection surfaces the collision in your review diff instead of silently
  clobbering or orphaning it.

Verify scans the **whole** output tree every run regardless, so a delta wouldn't
even speed up the expensive step. We therefore keep full projection as the
mechanism and add the commit-hash **report** for reviewer visibility — which is
the actual goal.

---

## Monorepo manifests (the lockfile leak)

Stripping a private **directory** does not remove that package's footprint from
shared monorepo manifests. `pnpm-workspace.yaml` still lists the private package
as a workspace member, and `pnpm-lock.yaml` still contains its full importer and
resolved dependency graph — e.g. `dashboard-saas`'s entire Next.js dep tree stays
in the public lockfile even though the `dashboard-saas/` directory is gone. That
is a real leak of private structure.

`assemble.sh` handles this automatically after stripping:

1. **Prunes private members** from `pnpm-workspace.yaml` (any workspace entry
   whose path is a private path, per the denylist).
2. **Regenerates `pnpm-lock.yaml`** for the remaining public workspace via
   `pnpm install --lockfile-only` — **offline first** (deterministic, from your
   local pnpm store; all remaining deps are already resolved so no network is
   needed), with a bounded online fallback only if the store is cold. It never
   writes `node_modules`.

`verify-oss.sh` then enforces it: the **build-manifest gate** fails if any file in
`MANIFEST_GLOBS` (lockfiles, `pnpm-workspace.yaml`, `package.json`,
`tsconfig*.json`) still references a private path. So even if regeneration is
skipped (pnpm missing / cold store offline), the push is blocked until the
manifests are clean — never a silent leak.

> **Benign name references are NOT scrubbed.** Ignore files (`.gitignore`,
> `.ocignore`, `.vercelignore`) and docs may mention a private directory *name*;
> that's harmless and intentional. The manifest gate only scans build manifests,
> where a private-path reference is always a real dependency leak.

---

## Prerequisites

- `git` and `tar` (standard on macOS/Linux; Windows: use Git Bash or WSL)
- **`pnpm`** — needed to regenerate the public lockfile. Offline regeneration
  uses your local pnpm store (warm because you develop in this repo). If the
  store is cold, assemble does one bounded online `pnpm install --lockfile-only`;
  if that also fails it warns and the verify gate blocks until you run
  `( cd <public> && pnpm install --lockfile-only )` manually.
- A secret scanner for the content gate — install one:
  - [`gitleaks`](https://github.com/gitleaks/gitleaks) (recommended), or
  - [`trufflehog`](https://github.com/trufflesecurity/trufflehog)
  - Without a scanner, `verify-oss.sh` warns and SKIPS the content scan — do not
    publish in that state; install gitleaks or run the `ecc:opensource-sanitizer`
    skill manually first.
- A local clone of the public repo (one-time):
  ```bash
  git clone git@github.com:Opencomplai/opencomplai.git ~/repos/opencomplai-public
  ```

---

## Day-to-day sync workflow

```bash
# 0. Commit everything you intend to publish (assemble refuses a dirty tree).

# 1. Report + assemble + verify + record marker, in one command (HARD GATE).
bash scripts/sync-oss.sh ~/repos/opencomplai-public

# 2. Review the change report it printed, then the diff in your editor.
code ~/repos/opencomplai-public

# 3. Commit and push MANUALLY only after approving the diff. Use the exact
#    commands the script printed (they include the OSS-Synced-From trailer):
cd ~/repos/opencomplai-public
git add -A
git status                       # confirm changed files match the report
git commit -m "chore: sync from enterprise @ $(date +%Y-%m-%d)

OSS-Synced-From: <sha printed by the script>"
git push origin main
```

Prefer the steps explicit? Run them yourself:

```bash
bash scripts/sync-report.sh . ~/repos/opencomplai-public   # what changed (read-only)
bash scripts/assemble.sh    . ~/repos/opencomplai-public   # build the tree
bash scripts/verify-oss.sh    ~/repos/opencomplai-public   # if this fails, STOP
```

(Running the steps by hand does **not** update `.oss-sync-state` — only
`sync-oss.sh` records the marker, and only after verify passes.)

If `git push` is **rejected** (non-fast-forward), the public repo has community
commits not yet imported to enterprise. Import them first (see below), then
re-run the sync. Because every sync is a full re-projection, re-running is always
safe even if the marker got ahead of what was actually pushed.

---

## Usage reference

### `sync-oss.sh`

```
bash scripts/sync-oss.sh <OUTPUT_DIR> [SOURCE_DIR]
```

Runs `sync-report.sh` → `assemble.sh` → `verify-oss.sh`, then (only on verify
PASS) writes the `.oss-sync-state` marker with enterprise `HEAD`. Never commits
or pushes — prints the manual commit/push commands. `SOURCE_DIR` defaults to `.`.

### `sync-report.sh`

```
bash scripts/sync-report.sh <SOURCE_DIR> [OUTPUT_DIR]
```

Read-only. Prints commits and changed files since the last synced commit, split
into "will appear in public sync" vs "stripped as private". Baseline resolution
order: local `.oss-sync-state` marker → `OSS-Synced-From` trailer in the public
repo's latest commit → none (initial sync). Transfers nothing.

### `assemble.sh`

```
bash scripts/assemble.sh <SOURCE_DIR> <OUTPUT_DIR>
```

- `<SOURCE_DIR>` — the enterprise repo root (usually `.`)
- `<OUTPUT_DIR>` — where to write the public tree (your public-repo clone)

Behavior:
1. Refuses to run if `SOURCE_DIR` is not a git repo or has uncommitted changes.
2. Exports tracked files from `HEAD` via `git archive`.
3. Strips private content: `dashboard-saas/`, `isms/`, `compliance-reports/`,
   `.claude/`, all of `.github/`, `vercel.json`, and `*.plan.md`.
4. Prunes private members from `pnpm-workspace.yaml` and regenerates
   `pnpm-lock.yaml` for the public workspace (offline-first). See
   [Monorepo manifests](#monorepo-manifests-the-lockfile-leak).
5. Preserves the public clone's `.git/` if `OUTPUT_DIR` already contains one.

### `verify-oss.sh`

```
bash scripts/verify-oss.sh <OUTPUT_DIR>
```

Exits **nonzero** (push forbidden) if any of these are present in the output:
a private directory/file/workflow, an internal `*.plan.md`, the `.oss-sync-state`
marker, a `.env` (other than `.env.example`), a secret-pattern file
(`*.key/.pem/.p12/.pfx/.tfstate/.db/.sql/.dump`), **a private-path reference in a
build manifest** (lockfile/workspace/`package.json`/`tsconfig`), a file over
25 MB, a secret found by the content scanner, or an empty tree. On success:
`PASS — N files ready to publish (secret scan clean)`.

### `oss-config.sh`

Sourced by the others; not run directly. Defines `PRIVATE_DIRS`,
`PRIVATE_FILES`, `PRIVATE_GLOBS`, `PRIVATE_WORKFLOWS`, `SECRET_GLOBS`,
`WORKSPACE_MANIFESTS`, `MANIFEST_GLOBS`, `MAX_FILE_BYTES`, `PUBLIC_REPO_URL`,
`SYNC_STATE_FILENAME`, `SYNC_TRAILER_KEY`, and the `oss_is_private` matcher.
**The only file to edit when the denylist changes.**

---

## Importing community contributions (public → enterprise)

When a community PR is merged on the public repo, import it back into enterprise
before the next sync (otherwise the next sync reverts it):

```bash
# one-time: add the public repo as a read-only remote
git remote add oss git@github.com:Opencomplai/opencomplai.git

git fetch oss
git cherry-pick <commit-sha>     # or: git merge oss/main
```

Treat every import as untrusted input — verify the CLA was signed, review the
full diff, scan for secrets, and review dependency/lockfile changes **before**
cherry-picking. Never import unsigned or un-CLA'd commits.

---

## Notes

- **Never push directly to the public repo by hand.** Only this workflow touches
  it; direct pushes cause non-fast-forward rejections on the next sync.
- **The marker is local and gitignored.** It is per-clone state, not shared. On a
  fresh machine the first sync reports against the `OSS-Synced-From` trailer in
  public history (if present) or treats the run as an initial full sync — either
  way the transfer is correct.
- The first/bootstrap publish is the highest-risk moment — run a full
  `ecc:opensource-sanitizer` audit over the assembled tree before the first push.
