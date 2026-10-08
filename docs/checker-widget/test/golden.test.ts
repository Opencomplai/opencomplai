/**
 * Golden-parity tests for the TypeScript checker engine.
 *
 * The vectors are loaded from
 * packages/core/tests/fixtures/checker_golden_vectors_shared.json (the file the
 * Python suites assert too) — the TS engine must
 * produce identical in_scope, is_high_risk, is_prohibited, effective_entity,
 * status_change ids, obligation ids, and determination_path for every case.
 *
 * If this suite fails after a Python-side engine change it means engine.ts has
 * drifted from engine.py and must be updated in the same commit.
 */
import { describe, it, expect } from "vitest";
import { evaluate, CHECKER_VERSION } from "../src/engine";

// ── version pin ───────────────────────────────────────────────────────────────
// Read CHECKER_VERSION from the Python source at test time so any version bump
// there automatically fails this test until the TS constant is updated.
import { readFileSync } from "node:fs";
import { resolve } from "node:path";

const pyInitPath = resolve(
  __dirname,
  "../../../packages/core/src/opencomplai_core/compliance_checker/models.py"
);
const pySource = readFileSync(pyInitPath, "utf-8");
const versionMatch = pySource.match(/CHECKER_VERSION\s*=\s*"([^"]+)"/);
const PY_CHECKER_VERSION = versionMatch?.[1];

it("CHECKER_VERSION matches Python models.py", () => {
  expect(CHECKER_VERSION).toBe(PY_CHECKER_VERSION);
});

// ── vectors ───────────────────────────────────────────────────────────────────
interface GoldenExpected {
  in_scope: boolean;
  is_high_risk: boolean;
  is_prohibited: boolean;
  effective_entity: string | null;
  status_change_ids: string[];
  obligation_ids: string[];
  determination_path: string[];
}

interface GoldenFixture {
  name: string;
  session: { answers: Record<string, unknown> };
  expected: GoldenExpected;
}

const vectorsPath = resolve(
  __dirname,
  "../../../packages/core/tests/fixtures/checker_golden_vectors_shared.json"
);
const FIXTURES: GoldenFixture[] = JSON.parse(
  readFileSync(vectorsPath, "utf-8")
).vectors;

// ── run ───────────────────────────────────────────────────────────────────────
describe(`TS engine golden parity (${FIXTURES.length} vectors)`, () => {
  for (const fixture of FIXTURES) {
    it(fixture.name, () => {
      const result = evaluate(fixture.session.answers);
      const exp = fixture.expected;

      expect(result.in_scope).toBe(exp.in_scope);
      expect(result.is_high_risk).toBe(exp.is_high_risk);
      expect(result.is_prohibited).toBe(exp.is_prohibited);
      expect(result.effective_entity).toBe(exp.effective_entity);
      expect(result.status_changes.map((s) => s.id)).toEqual(exp.status_change_ids);
      expect(result.obligations.map((o) => o.id)).toEqual(exp.obligation_ids);
      expect(result.determination_path).toEqual(exp.determination_path);
    });
  }
});
