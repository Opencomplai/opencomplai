# Prohibited demo

A fictional system that ranks citizens by their behaviour. Its purpose matches the
EU AI Act Art. 5 prohibition on social scoring, so the gate refuses it outright.

```bash
opencomplai check -m system-manifest.json
```

Expected exit code: **3** (POLICY_BLOCK). A prohibited system cannot be accepted:
`opencomplai accept` refuses it.

These are fictional systems and an illustrative sandbox classification, not a legal classification or legal advice.
