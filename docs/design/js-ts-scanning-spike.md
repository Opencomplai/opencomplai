# Design Spike: JS/TS Repo Scanning (Execution Plan 3.4)

**Status:** Design spike only — no implementation in this pass, per the plan's explicit
recommendation to design before committing to full implementation.

## Grounding facts (verified against the repo)

1. **`RepoInventory` is already language-aware.** `packages/core/src/opencomplai_core/scanner/inventory.py`'s
   `LANGUAGE_BY_EXT` dict already maps `.js` → `javascript`, `.ts`/`.tsx` → `typescript`, `.jsx` → `javascript`
   (lines 24-42). Every `InventoryEntry` already carries a `language` field populated from this map. **The
   file-walking/inventory layer requires zero changes** to support JS/TS — it already classifies these files
   correctly today; they are simply never extracted or detected on.

2. **`BaseDetector.supported_languages` is declared but never enforced anywhere.** Confirmed via repo-wide
   search: every existing detector (`ai_dependency.py`, `artifact.py`, `ast_usage.py`, `biometric.py`,
   `dataflow.py`, `endpoint.py`, `framework_ast.py`, `semantic.py`) implements the abstract property
   (all currently return `frozenset({"python"})`), but no live code in `scan_engine.py` or `features.py` ever
   reads `.supported_languages` to skip a detector or filter its input. The actual Python-only gate lives
   entirely inside `extractors/ast.py`'s own filter: `if entry.language != "python": continue` (both in
   `_collect_ast()` and `extract_ast_framework_objects()`). This means `supported_languages` is currently
   **dead metadata** — a real JS/TS rollout should either (a) start enforcing it centrally in
   `scan_engine.py`/`features.py` so detectors can declare "python only" vs "js/ts capable" and be
   dispatched correctly, or (b) keep the per-extractor filtering pattern and accept that
   `supported_languages` remains advisory-only documentation. Recommend (a) for JS/TS work, since it turns
   dead metadata into an actual dispatch mechanism and avoids each new detector re-implementing its own
   language filter ad hoc.

3. **Only one extractor module exists today: `extractors/ast.py` (Python `ast` module-based).** There is no
   `extractors/ast_js.py` or equivalent. A JS/TS extractor needs its own AST parser — Python's stdlib `ast`
   module cannot parse JavaScript/TypeScript. This is the core new-code surface.

4. **`FeatureStore`'s shape is language-agnostic already.** `ImportRef`, `CallsiteRef`, `ConfigRef`, etc.
   (`feature_types.py`) are all plain dataclasses keyed by `module`/`name`/`location`/`scope` — nothing in
   their shape assumes Python. A JS/TS extractor can populate the *same* `FeatureStore.imports`/`.callsites`
   lists using the *same* dataclasses, which means `AstUsageDetector` (lexical import/callsite matching)
   and `FrameworkAstDetector`'s underlying data model would work unmodified against JS/TS-sourced
   `ImportRef`/`CallsiteRef` entries, IF a JS/TS extractor populates them in a compatible shape.

## Proposed architecture (not implemented — design only)

### New module: `packages/core/src/opencomplai_core/scanner/extractors/ast_js.py`

- Parse `.js`/`.jsx`/`.ts`/`.tsx` files using a JS/TS-capable parser. Python has no built-in JS/TS AST parser,
  so this requires either:
  - **(a) A pure-Python JS/TS tokenizer/parser library** (e.g. a minimal ES2020+ subset parser) — keeps the
    scanner dependency-free of Node.js, but is a substantial parser-correctness undertaking and a new
    third-party Python dependency to vet.
  - **(b) Shelling out to a Node.js-based parser** (e.g. invoking `@babel/parser` or `typescript`'s own
    compiler API via a small Node.js helper script, similar in spirit to how
    `docs/checker-widget/build.mjs` is already invoked as a Node subprocess elsewhere in this repo) — reuses
    battle-tested JS/TS parsing, but makes the core Python scanner depend on a Node.js runtime being present,
    which is a meaningfully different deployment/air-gap story than the current pure-Python scanner
    (relevant to the "air-gap ready" moat guarantee — must be confirmed opt-in, not a hard new requirement
    for the base scan path).
  - **Recommendation:** (b), gated behind an opt-in flag (mirroring 1.4's `--framework-detectors` and 2.6's
    `--provider` precedent in this plan) — e.g. `--js-ts` on `scan_cmd` — so the default Python-only scan
    path has no new runtime dependency. This is consistent with how this plan has repeatedly handled
    "new capability that changes the dependency/runtime footprint" (opt-in flag, not a default-path change).

- Populate `ImportRef`/`CallsiteRef` from `import`/`require`/dynamic `import()` statements and call
  expressions, following the exact same dataclass shapes `extractors/ast.py` already produces for Python.

### Detector changes

- Extend `AstUsageDetector.supported_languages` to include `"javascript"`/`"typescript"` once a JS/TS
  extractor exists and is proven correct on fixtures — no change to the detector's matching logic itself,
  since it already operates generically on `FeatureStore.imports`/`.callsites` regardless of source language.
- `FrameworkAstDetector` (1.4) would need its own JS/TS-aware binding-join logic — the current
  `_FrameworkObjectVisitor` is a Python `ast.NodeVisitor` subclass and cannot run against JS/TS source; a
  JS/TS equivalent would need its own visitor built on whatever parser is chosen above. This is real,
  non-trivial new code, not just a `supported_languages` flag flip.

### Central dispatch (recommended, addresses point 2 above)

- Add a `supported_languages` check in `features.py::extract_features()` (or `scan_engine.py`) so each
  detector's `detect()` is only invoked when at least one language present in the scanned repo intersects
  its declared `supported_languages` — turning today's dead metadata into a real, enforced gate. This is a
  small, additive change (a `set.intersection` check before calling `detector.detect(features)`) that
  should land regardless of whether JS/TS support ships, since it fixes existing dead code.

## Acceptance criteria for a future full implementation (not attempted here)

- Existing Python-only detector tests remain green (no regression) — should hold trivially since nothing
  described above modifies the Python extractor or existing detectors' matching logic.
- A new JS/TS fixture repo (e.g. `import OpenAI from 'openai'` in a `.ts` file) produces evidence from at
  least the `ast_usage`-equivalent detector, once the new extractor and opt-in flag are implemented.

## Risk to the moat

Large surface area, as the plan itself flags. The Node.js-dependency question (option b above) is the single
highest-leverage design decision — it directly affects the "air-gap ready" claim if not kept strictly opt-in.
No further action recommended beyond this spike until a human decides between options (a) and (b) above and
scopes the actual implementation as its own deliverable.
