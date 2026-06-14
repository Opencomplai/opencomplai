# Requirements

## For CLI and SDK (local mode)

| Requirement | Version | Notes |
|---|---|---|
| Python | 3.11+ | Check with `python3 --version` |
| pip | Latest | Bundled with Python |

Optional but recommended:

- **[uv](https://github.com/astral-sh/uv)** — faster Python package manager used by the monorepo toolchain.
- **[Git](https://git-scm.com/)** — required for `--commit-ref` in `opencomplai check`.

## For the full Docker deployment

| Requirement | Version |
|---|---|
| Docker | 24+ |
| Docker Compose | v2 |
| RAM | 4 GB |
| Disk | 10 GB free |

## For contributors

| Requirement | Version |
|---|---|
| Python | 3.11+ |
| Node.js | 20 LTS |
| pnpm | 9+ |
| uv | Latest |
| Docker | 24+ |
| pre-commit | Latest |

Run `./scripts/bootstrap.sh` after cloning to install all dependencies automatically.

## Verify your Python version

```bash
python3 --version
# Python 3.11.x or higher
```