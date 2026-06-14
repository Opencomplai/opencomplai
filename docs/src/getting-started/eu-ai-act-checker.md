# EU AI Act applicability checker
<div class="ococ-privacy-banner" style="font-size:0.85rem;color:var(--md-default-fg-color--light,#555);margin-bottom:1rem;">
  Runs entirely in your browser. Your answers are never transmitted.
</div>

Answer a short questionnaire to find out whether the EU AI Act applies to your
AI system, in what operator role, at what risk tier, and which obligations follow.

The engine is a direct port of the
[Future of Life Institute compliance checker](https://futuroflife.institute)
flowchart (version **fli-2025-07-28**), verified against 17 golden test cases
that run in CI on every commit.

---

<div id="ococ-checker">
  <noscript>
    <p><strong>JavaScript is required to run the interactive checker.</strong></p>
    <p>You can also run it from the CLI: <code>opencomplai checker</code></p>
  </noscript>
  <p style="color:var(--md-default-fg-color--light,#666);font-size:0.9rem;">
    Loading checker…
  </p>
</div>

---

## Use from the CLI instead

```bash
# Interactive wizard (same questions, same engine)
opencomplai checker

# Open this page in your browser directly
opencomplai checker --web

# Serve the checker locally and open it (no internet required)
opencomplai checker --web --local

# Replay a saved answer set (for CI or repeatable demos)
opencomplai checker --answers answers.json -o json

# Export a full report
opencomplai checker --answers answers.json --export-all ./reports/eu-ai-act-result
```

## What happens after the checker?

Once you know your role and risk tier, the next step is declaring a manifest:

```bash
# Let the checker pre-fill the manifest for you
opencomplai checker --answers answers.json --write-manifest system-manifest.json

# Or initialise interactively (runs the checker first)
opencomplai init --interactive
```

Then run the compliance gate:

```bash
opencomplai check
```

See the [quick start](quick-start.md) for the full flow.

## Disclaimer

!!! note "Not legal advice"
    This tool automates the Future of Life Institute compliance checker logic
    for educational and planning purposes. It does not constitute legal advice.
    Seek qualified legal counsel and follow national guidance for formal compliance
    decisions. Opencomplai is not affiliated with the Future of Life Institute or
    the European Union.
