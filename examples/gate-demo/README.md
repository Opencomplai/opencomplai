# Gate demo (sandbox)

Five tiny fictional systems, one per gate outcome. Each directory holds a
`system-manifest.json` and a README with the exact command. Run `opencomplai check`
from inside the directory.

| Directory | Command | Exit | Meaning |
|---|---|---|---|
| [prohibited](prohibited/README.md) | `check -m system-manifest.json` | 3 | Prohibited practice (Art. 5): blocked |
| [trap](trap/README.md) | `check -m system-manifest.json --change-context model_retrain` | 4 | Modification trap: halted for human review |
| [high-risk](high-risk/README.md) | `check -m system-manifest.json` | 1 | High-risk classification not accepted |
| [accepted](accepted/README.md) | `check -m system-manifest.json --repo-root .` (after `accept`) | 1 | Art. 6 cleared; other EU obligations still Missing |
| [limited](limited/README.md) | `check -m system-manifest.json` | 0 | No gate failure |

An acceptance acknowledges the classification only; it does not make a system compliant.
See [exit codes](../../docs/src/cli/exit-codes.md).

The systems and purposes are fictional and the classification is an illustrative
sandbox, not legal advice.
