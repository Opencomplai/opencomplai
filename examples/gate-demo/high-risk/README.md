# High-risk demo

A fictional credit scoring system for loan applications. Credit scoring is an
Annex III high-risk purpose, so `check` fails the Art. 6 row until a human accepts
the classification.

```bash
opencomplai check -m system-manifest.json
```

Expected exit code: **1** (CONTROL_FAIL), with `failed_controls` listing the Art. 6
rows. For the accept step, see `../accepted`.

These are fictional systems and an illustrative sandbox classification, not a legal classification or legal advice.
