# `opencomplai serve`

**What it does:** starts a tiny localhost dashboard so you can run scans and
browse recent history without leaving your laptop.

**When to use it:** day-to-day developer feedback while iterating on a repo.

**Don't:** confuse this with Pro / `dashboard enroll` / `dashboard-saas`. Serve
never talks to SaaS ingest, never holds tenant tokens, and binds to
`127.0.0.1` only.

## Install

```bash
pip install 'opencomplai[serve]'
# or: pip install 'opencomplai-cli[serve]'
```

## Example

```bash
opencomplai serve .
# open http://127.0.0.1:8420/
```

History is stored under `~/.opencomplai/scan-history/` (capped at 50 runs per
project).
