/**
 * Golden-parity tests for the TypeScript checker engine.
 *
 * Each fixture is the same JSON file used by
 * packages/core/tests/test_compliance_checker_golden.py — the TS engine must
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

// ── fixture types ─────────────────────────────────────────────────────────────
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

// ── inline all 17 fixtures ────────────────────────────────────────────────────
// Inlined (rather than dynamic import) so vitest works without extra config.
const FIXTURES: GoldenFixture[] = [
  {
    name: "01_auth_rep_only",
    session: { answers: { gate_is_ai_system: true, e1_entity_type: "authorised_rep" } },
    expected: {
      in_scope: true, is_high_risk: false, is_prohibited: false,
      effective_entity: "authorised_rep",
      status_change_ids: [],
      obligation_ids: ["authorised_representative"],
      determination_path: ["gate:yes", "e1:authorised_rep"],
    },
  },
  {
    name: "02_out_of_scope_not_ai",
    session: { answers: { gate_is_ai_system: false } },
    expected: {
      in_scope: false, is_high_risk: false, is_prohibited: false,
      effective_entity: null,
      status_change_ids: ["out_of_scope"],
      obligation_ids: [],
      determination_path: ["gate:no"],
    },
  },
  {
    name: "03_out_of_scope_s1",
    session: { answers: { gate_is_ai_system: true, e1_entity_type: "provider", s1_in_scope: false } },
    expected: {
      in_scope: false, is_high_risk: false, is_prohibited: false,
      effective_entity: "provider",
      status_change_ids: ["out_of_scope"],
      obligation_ids: [],
      determination_path: ["gate:yes", "e1:provider", "s1:none"],
    },
  },
  {
    name: "04_out_of_scope_excluded",
    session: { answers: { gate_is_ai_system: true, e1_entity_type: "provider", s1_in_scope: true, r2_excluded: true } },
    expected: {
      in_scope: false, is_high_risk: false, is_prohibited: false,
      effective_entity: "provider",
      status_change_ids: ["out_of_scope"],
      obligation_ids: [],
      determination_path: ["gate:yes", "e1:provider", "s1:in_scope", "r2:excluded"],
    },
  },
  {
    name: "05_prohibited",
    session: { answers: { gate_is_ai_system: true, e1_entity_type: "provider", hr2_annex_iii: true, s1_in_scope: true, r3_prohibited: true } },
    expected: {
      in_scope: true, is_high_risk: true, is_prohibited: true,
      effective_entity: "provider",
      status_change_ids: ["high_risk", "prohibited"],
      obligation_ids: ["prohibited"],
      determination_path: ["gate:yes", "e1:provider", "hr:high_risk", "s1:in_scope", "r3:prohibited"],
    },
  },
  {
    name: "06_high_risk_provider",
    session: { answers: { gate_is_ai_system: true, e1_entity_type: "provider", hr2_annex_iii: true, s1_in_scope: true } },
    expected: {
      in_scope: true, is_high_risk: true, is_prohibited: false,
      effective_entity: "provider",
      status_change_ids: ["high_risk"],
      obligation_ids: ["ai_literacy", "provider_high_risk"],
      determination_path: ["gate:yes", "e1:provider", "hr:high_risk", "s1:in_scope", "e1:ai_literacy"],
    },
  },
  {
    name: "07_high_risk_deployer_fria",
    session: { answers: { gate_is_ai_system: true, e1_entity_type: "deployer", hr2_annex_iii: true, s1_in_scope: true, r5_fria: true } },
    expected: {
      in_scope: true, is_high_risk: true, is_prohibited: false,
      effective_entity: "deployer",
      status_change_ids: ["high_risk", "high_risk_exception"],
      obligation_ids: ["ai_literacy", "deployer_high_risk", "deployer_general", "fria"],
      determination_path: ["gate:yes", "e1:deployer", "hr:high_risk", "s1:in_scope", "s1:high_risk_exception", "e1:ai_literacy", "r5:fria"],
    },
  },
  {
    name: "08_become_provider",
    session: { answers: { gate_is_ai_system: true, e1_entity_type: "deployer", e2_modifications: true, hr2_annex_iii: true, s1_in_scope: true } },
    expected: {
      in_scope: true, is_high_risk: true, is_prohibited: false,
      effective_entity: "provider",
      status_change_ids: ["become_provider", "high_risk"],
      obligation_ids: ["ai_literacy", "provider_high_risk"],
      determination_path: ["gate:yes", "e1:deployer", "e2:become_provider", "hr:high_risk", "s1:in_scope", "e1:ai_literacy"],
    },
  },
  {
    name: "09_gpai_provider",
    session: { answers: { gate_is_ai_system: true, e1_entity_type: "provider", s1_in_scope: true, s1_gpai: true } },
    expected: {
      in_scope: true, is_high_risk: false, is_prohibited: false,
      effective_entity: "provider",
      status_change_ids: ["gpai"],
      obligation_ids: ["ai_literacy", "gpai_provider"],
      determination_path: ["gate:yes", "e1:provider", "s1:in_scope", "e1:ai_literacy", "r1:gpai"],
    },
  },
  {
    name: "10_gpai_systemic_risk",
    session: { answers: { gate_is_ai_system: true, e1_entity_type: "provider", s1_in_scope: true, s1_gpai: true, s1_gpai_systemic_risk: true } },
    expected: {
      in_scope: true, is_high_risk: false, is_prohibited: false,
      effective_entity: "provider",
      status_change_ids: ["gpai"],
      obligation_ids: ["ai_literacy", "gpai_provider", "gpai_systemic_risk"],
      determination_path: ["gate:yes", "e1:provider", "s1:in_scope", "e1:ai_literacy", "r1:gpai", "r1:gpai_systemic_risk"],
    },
  },
  {
    name: "11_transparency_only_deployer",
    session: { answers: { gate_is_ai_system: true, e1_entity_type: "deployer", s1_in_scope: true, r4_transparency: true } },
    expected: {
      in_scope: true, is_high_risk: false, is_prohibited: false,
      effective_entity: "deployer",
      status_change_ids: [],
      obligation_ids: ["ai_literacy", "deployer_general", "transparency"],
      determination_path: ["gate:yes", "e1:deployer", "s1:in_scope", "e1:ai_literacy", "r4:transparency"],
    },
  },
  {
    name: "12_product_manufacturer_out_of_scope",
    session: { answers: { gate_is_ai_system: true, e1_entity_type: "product_manufacturer", e3_product_integration: "none" } },
    expected: {
      in_scope: false, is_high_risk: false, is_prohibited: false,
      effective_entity: "product_manufacturer",
      status_change_ids: ["out_of_scope"],
      obligation_ids: [],
      determination_path: ["gate:yes", "e1:product_manufacturer", "e3:none"],
    },
  },
  {
    name: "13_high_risk_exception_deployer",
    session: { answers: { gate_is_ai_system: true, e1_entity_type: "deployer", hr2_annex_iii: true, hr1_annex_i: false, s1_in_scope: true, s1_scope_region: "eu" } },
    expected: {
      in_scope: true, is_high_risk: true, is_prohibited: false,
      effective_entity: "deployer",
      status_change_ids: ["high_risk", "high_risk_exception"],
      obligation_ids: ["ai_literacy", "deployer_high_risk", "deployer_general"],
      determination_path: ["gate:yes", "e1:deployer", "hr:high_risk", "s1:in_scope", "s1:high_risk_exception", "e1:ai_literacy"],
    },
  },
  {
    name: "14_distributor_high_risk",
    session: { answers: { gate_is_ai_system: true, e1_entity_type: "distributor", hr2_annex_iii: true, s1_in_scope: true } },
    expected: {
      in_scope: true, is_high_risk: true, is_prohibited: false,
      effective_entity: "distributor",
      status_change_ids: ["high_risk"],
      obligation_ids: ["distributor"],
      determination_path: ["gate:yes", "e1:distributor", "hr:high_risk", "s1:in_scope"],
    },
  },
  {
    name: "15_distributor_not_high_risk",
    session: { answers: { gate_is_ai_system: true, e1_entity_type: "distributor", s1_in_scope: true } },
    expected: {
      in_scope: true, is_high_risk: false, is_prohibited: false,
      effective_entity: "distributor",
      status_change_ids: [],
      obligation_ids: [],
      determination_path: ["gate:yes", "e1:distributor", "s1:in_scope"],
    },
  },
  {
    name: "16_handover_provider",
    session: { answers: { gate_is_ai_system: true, e1_entity_type: "provider", e2_modifications: true, hr2_annex_iii: true, s1_in_scope: true } },
    expected: {
      in_scope: true, is_high_risk: true, is_prohibited: false,
      effective_entity: "provider",
      status_change_ids: ["handover", "high_risk"],
      obligation_ids: ["ai_literacy", "provider_high_risk"],
      determination_path: ["gate:yes", "e1:provider", "e2:handover", "hr:high_risk", "s1:in_scope", "e1:ai_literacy"],
    },
  },
  {
    name: "17_hr6_not_high_risk",
    session: { answers: { gate_is_ai_system: true, e1_entity_type: "provider", hr2_annex_iii: true, hr6_accessory: true, s1_in_scope: true } },
    expected: {
      in_scope: true, is_high_risk: false, is_prohibited: false,
      effective_entity: "provider",
      status_change_ids: [],
      obligation_ids: ["ai_literacy"],
      determination_path: ["gate:yes", "e1:provider", "s1:in_scope", "e1:ai_literacy"],
    },
  },
];

// ── run ───────────────────────────────────────────────────────────────────────
describe("TS engine golden parity (17 fixtures)", () => {
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
