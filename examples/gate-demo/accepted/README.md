# Accepted demo

A fictional road traffic infrastructure controller (an Annex III high-risk purpose).
Run the check, accept the classification with a throw-away key, then run it again.
Nothing here is committed: no key and no acceptance record.

```bash
cp -r . /tmp/gate-demo-accepted && cd /tmp/gate-demo-accepted
opencomplai check -m system-manifest.json --repo-root .
# failed_controls: EU_AIA_ART6_HIGH_RISK        (exit 1)

# --key: your signing key (the one 'opencomplai init' created works); never commit it
opencomplai accept -m system-manifest.json --accepted-by you@example.test \
  --statement "Illustrative sandbox acceptance" --repo-root . --key ~/.opencomplai/signing.key
opencomplai check -m system-manifest.json --repo-root .
# failed_controls: Art. 9, Art. 11, Art. 12, Art. 13, ... Art. 73   (exit 1)
```

After `accept`, the Art. 6 row is cleared. The run still exits 1 because the other EU obligations are Missing: an acceptance acknowledges the classification only and does not make a system compliant.

These are fictional systems and an illustrative sandbox classification, not a legal classification or legal advice.
