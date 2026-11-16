# Per-pack fixtures

One directory per framework pack, named by the pack key:

```
packs/<KEY>/
  manifest.json          system manifest; compliance_targets is [<KEY>]
  empty/                 repo tree holding only .gitkeep
  scaffolded/            repo tree with the expected files, still empty
  evidenced/             repo tree with real evidence
  applicability/<outcome>.json   optional; one manifest per reachable outcome
```

A pack is discovered when `<KEY>/manifest.json` exists. The harness is
`packages/cli/tests/test_pack_goldens.py`. Each case copies a repo tree to a
temp directory, adds `manifest.json` as `system-manifest.json` and runs the
CLI there. An `applicability/<outcome>.json` manifest carries the scope
answers that reach that outcome; `scope <KEY>` is run on it.

The golden files for the same key live in
`packages/cli/tests/golden/packs/<KEY>/`; see the README there.

## Rule

A pack card edits only its own two directories: `packs/<KEY>/` here and
`golden/packs/<KEY>/` in the CLI tests. It never edits the shared test.

## Update

```sh
OPENCOMPLAI_UPDATE_PACK_GOLDEN=<KEY> uv run pytest packages/cli/tests/test_pack_goldens.py -k <KEY>
```

This rewrites that key's golden directory and nothing else.
