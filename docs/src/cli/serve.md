# `opencomplai serve`

**What it does:** starts a tiny localhost dashboard so you can run scans and
browse recent history without leaving your laptop.

**When to use it:** day-to-day developer feedback while iterating on a repo.

**Don't:** confuse this with Pro / `dashboard enroll` / `dashboard-saas`. Serve
never talks to SaaS ingest, never holds tenant tokens, and binds to
loopback only (`127.0.0.1` / `localhost`).

## Install

```bash
pip install 'opencomplai[serve]'
# or: pip install 'opencomplai-cli[serve]'
```

The `serve` extra pulls in `uvicorn`. Without it the command exits `2` and
tells you to install the extra.

## Synopsis

```bash
opencomplai serve [PROJECT_ROOT] [OPTIONS]
```

## Arguments

| Argument | Default | Description |
|---|---|---|
| `PROJECT_ROOT` | `.` | Project directory to scan. Must stay on this machine. |

## Options

| Option | Default | Description |
|---|---|---|
| `--host` | `127.0.0.1` | Loopback host only. Values other than `127.0.0.1` or `localhost` are rejected (exit `2`). |
| `--port` | `8420` | Local TCP port for the dashboard. |

Run `opencomplai serve --help` for the same list.

## Example

```bash
opencomplai serve .
# open http://127.0.0.1:8420/

opencomplai serve . --host 127.0.0.1 --port 8420
```

History is stored under `~/.opencomplai/scan-history/` (capped at 50 runs per
project).
