/**
 * TypeScript port of packages/core/src/opencomplai_core/compliance_checker/engine.py
 * Deterministic compliance checker — checker version checker-2026-10-26.
 *
 * Must produce identical output to the Python evaluate() for all golden
 * vectors in packages/core/tests/fixtures/checker_golden_vectors_shared.json.
 */
import {
  getObligation,
  getStatusChange,
  ObligationItem,
  StatusChangeItem,
} from "./catalog";

export const CHECKER_VERSION = "checker-2026-10-26";

export type EntityType =
  | "provider"
  | "deployer"
  | "distributor"
  | "importer"
  | "product_manufacturer"
  | "authorised_rep";

export interface CheckerResult {
  checker_version: string;
  in_scope: boolean;
  is_high_risk: boolean;
  is_prohibited: boolean;
  effective_entity: EntityType | null;
  status_changes: StatusChangeItem[];
  obligations: ObligationItem[];
  determination_path: string[];
  answers: Record<string, unknown>;
  session_id: string | null;
  /** For each obligation id, the answer keys that made it apply. */
  obligation_basis: Record<string, string[]>;
}

// ── helpers ──────────────────────────────────────────────────────────────────

function answerBool(
  answers: Record<string, unknown>,
  key: string,
  defaultVal = false
): boolean {
  const v = answers[key];
  if (v === undefined || v === null) return defaultVal;
  if (typeof v === "boolean") return v;
  if (typeof v === "string") return ["true", "yes", "1"].includes(v.toLowerCase());
  return Boolean(v);
}

function answerEntity(answers: Record<string, unknown>): EntityType {
  const raw = answers["e1_entity_type"];
  if (typeof raw === "string") return raw as EntityType;
  return "provider";
}

function determineHighRisk(answers: Record<string, unknown>): boolean {
  // Art. 6(1) is conjunctive: an Annex I product is high-risk only if it has
  // an AI safety component AND is required to undergo third-party conformity
  // assessment. hr1 alone (self-certified Annex I product) does not trigger
  // high-risk.
  const hr1 =
    answerBool(answers, "hr1_annex_i") &&
    answerBool(answers, "hr8_conformity_assessment");
  const hr2 = answerBool(answers, "hr2_annex_iii");
  if (!hr1 && !hr2) return false;
  // Art. 6(3) final subparagraph: an Annex III system that performs profiling
  // of natural persons is always high-risk, overriding the (a)-(d) exceptions
  // below. Must be evaluated ahead of them.
  if (hr2 && answerBool(answers, "hr7_profiling")) return true;
  // The Art. 6(3)(a)-(d) exceptions are an Annex III derogation only (final
  // subparagraph of Art. 6(3)); an Annex I trigger has no such exception.
  if (hr2 && !hr1) {
    if (answerBool(answers, "hr3_art_6_3")) return false;
    if (answerBool(answers, "hr4_narrow_task")) return false;
    if (answerBool(answers, "hr5_no_significant_risk")) return false;
    if (answerBool(answers, "hr6_accessory")) return false;
  }
  return true;
}

function reliesOnArt63Derogation(answers: Record<string, unknown>): boolean {
  // Annex III system the provider assesses as not high-risk (Art. 6(3)).
  const annexI =
    answerBool(answers, "hr1_annex_i") &&
    answerBool(answers, "hr8_conformity_assessment");
  return (
    answerBool(answers, "hr2_annex_iii") &&
    !annexI &&
    !answerBool(answers, "hr7_profiling") &&
    ["hr3_art_6_3", "hr4_narrow_task", "hr5_no_significant_risk", "hr6_accessory"].some(
      (k) => answerBool(answers, k)
    )
  );
}

function dedupeIds(ids: string[]): string[] {
  const seen = new Set<string>();
  return ids.filter((id) => {
    if (seen.has(id)) return false;
    seen.add(id);
    return true;
  });
}

function dedupeObligations(items: ObligationItem[]): ObligationItem[] {
  const seen = new Set<string>();
  return items.filter((item) => {
    if (seen.has(item.id)) return false;
    seen.add(item.id);
    return true;
  });
}

function dedupeStatusChanges(items: StatusChangeItem[]): StatusChangeItem[] {
  const seen = new Set<string>();
  return items.filter((item) => {
    if (seen.has(item.id)) return false;
    seen.add(item.id);
    return true;
  });
}

function buildResult(opts: {
  in_scope: boolean;
  path: string[];
  statusIds: string[];
  obligationIds: string[];
  is_high_risk?: boolean;
  is_prohibited?: boolean;
  effective_entity?: EntityType | null;
  answers: Record<string, unknown>;
  obligation_basis?: Record<string, string[]>;
}): CheckerResult {
  return {
    checker_version: CHECKER_VERSION,
    in_scope: opts.in_scope,
    is_high_risk: opts.is_high_risk ?? false,
    is_prohibited: opts.is_prohibited ?? false,
    effective_entity: opts.effective_entity ?? null,
    status_changes: dedupeStatusChanges(
      opts.statusIds.map((id) => getStatusChange(id))
    ),
    obligations: dedupeObligations(
      opts.obligationIds.map((id) => getObligation(id))
    ),
    determination_path: opts.path,
    answers: opts.answers,
    session_id: null,
    obligation_basis: opts.obligation_basis ?? {},
  };
}

function entityObligations(
  entity: EntityType,
  isHighRisk: boolean
): string[] {
  const ids: string[] = [];
  if (entity === "provider") {
    if (isHighRisk) ids.push("provider_high_risk");
  } else if (entity === "deployer") {
    // Art. 26 binds deployers of high-risk systems only: one entry. The
    // catalogue keeps deployer_general for results from older versions.
    if (isHighRisk) ids.push("deployer_high_risk");
  } else if (entity === "distributor") {
    if (isHighRisk) ids.push("distributor");
  } else if (entity === "importer") {
    if (isHighRisk) ids.push("importer");
  } else if (entity === "product_manufacturer") {
    ids.push("product_manufacturer");
    if (isHighRisk) ids.push("provider_high_risk");
  }
  return ids;
}

// ── main evaluate ─────────────────────────────────────────────────────────────

export function evaluate(answers: Record<string, unknown>): CheckerResult {
  const path: string[] = [];
  const statusIds: string[] = [];
  const obligationIds: string[] = [];

  // Gate: is this an AI system?
  if (!answerBool(answers, "gate_is_ai_system", true)) {
    path.push("gate:no");
    return buildResult({
      in_scope: false,
      path,
      statusIds: ["out_of_scope"],
      obligationIds: [],
      answers,
    });
  }
  path.push("gate:yes");

  const entity = answerEntity(answers);
  let effectiveEntity: EntityType = entity;
  path.push(`e1:${entity}`);

  // Authorised representative short-circuit
  if (entity === "authorised_rep") {
    return buildResult({
      in_scope: true,
      path,
      statusIds: [],
      obligationIds: ["authorised_representative"],
      effective_entity: effectiveEntity,
      answers,
      obligation_basis: { authorised_representative: ["e1_entity_type"] },
    });
  }

  // Substantial modifications
  if (answerBool(answers, "e2_modifications")) {
    if (entity === "provider") {
      statusIds.push("handover");
      path.push("e2:handover");
    } else {
      statusIds.push("become_provider");
      effectiveEntity = "provider";
      path.push("e2:become_provider");
    }
  }

  // Product manufacturer with no integration → out of scope
  if (entity === "product_manufacturer") {
    const integration = answers["e3_product_integration"] ?? "none";
    if (integration === "none") {
      path.push("e3:none");
      return buildResult({
        in_scope: false,
        path,
        statusIds: dedupeIds([...statusIds, "out_of_scope"]),
        obligationIds: [],
        effective_entity: entity,
        answers,
      });
    }
  }

  const isHighRisk = determineHighRisk(answers);
  if (isHighRisk) {
    statusIds.push("high_risk");
    path.push("hr:high_risk");
  }

  // Geographic scope
  if (!answerBool(answers, "s1_in_scope", true)) {
    path.push("s1:none");
    return buildResult({
      in_scope: false,
      path,
      statusIds: dedupeIds([...statusIds, "out_of_scope"]),
      obligationIds: [],
      is_high_risk: isHighRisk,
      effective_entity: effectiveEntity,
      answers,
    });
  }
  path.push("s1:in_scope");

  // High-risk exception for EU deployers (Annex III only, no Annex I)
  const scopeRegion = answers["s1_scope_region"] ?? "eu";
  const hr1 = answerBool(answers, "hr1_annex_i");
  const hr2 = answerBool(answers, "hr2_annex_iii");
  if (
    effectiveEntity === "deployer" &&
    scopeRegion === "eu" &&
    hr2 &&
    !hr1 &&
    isHighRisk
  ) {
    statusIds.push("high_risk_exception");
    path.push("s1:high_risk_exception");
  }

  // Excluded
  if (answerBool(answers, "r2_excluded")) {
    path.push("r2:excluded");
    return buildResult({
      in_scope: false,
      path,
      statusIds: dedupeIds([...statusIds, "out_of_scope"]),
      obligationIds: [],
      is_high_risk: isHighRisk,
      effective_entity: effectiveEntity,
      answers,
    });
  }

  // Prohibited
  if (answerBool(answers, "r3_prohibited")) {
    path.push("r3:prohibited");
    return buildResult({
      in_scope: true,
      path,
      statusIds: dedupeIds([...statusIds, "prohibited"]),
      obligationIds: ["prohibited"],
      is_high_risk: isHighRisk,
      is_prohibited: true,
      effective_entity: effectiveEntity,
      answers,
      obligation_basis: { prohibited: ["r3_prohibited"] },
    });
  }

  // AI literacy for provider + deployer. A product manufacturer with an AI
  // system built in is treated as its provider (Art. 25), so Art. 4 applies.
  if (
    effectiveEntity === "provider" ||
    effectiveEntity === "deployer" ||
    effectiveEntity === "product_manufacturer"
  ) {
    obligationIds.push("ai_literacy");
    path.push("e1:ai_literacy");
  }

  // GPAI
  if (answerBool(answers, "s1_gpai")) {
    statusIds.push("gpai");
    obligationIds.push("gpai_provider");
    path.push("r1:gpai");
    if (answerBool(answers, "s1_gpai_systemic_risk")) {
      obligationIds.push("gpai_systemic_risk");
      path.push("r1:gpai_systemic_risk");
    }
  }

  // Entity-role obligations
  obligationIds.push(...entityObligations(effectiveEntity, isHighRisk));
  // A substantial modification moves a product manufacturer onto the provider
  // route; its own Art. 25(1) obligation still applies.
  if (entity === "product_manufacturer" && effectiveEntity !== entity) {
    obligationIds.push("product_manufacturer");
  }

  if (effectiveEntity === "provider" && reliesOnArt63Derogation(answers)) {
    obligationIds.push("provider_art_6_4_registration");
    path.push("hr:derogation_registration");
  }

  // Transparency — Art. 50 disclosure duties apply in addition to high-risk
  // obligations, not instead of them, so they are never gated on isHighRisk.
  // Only the "transparency_only" status (sole obligation tier) stays
  // high-risk-gated.
  const transparencyIds = transparencyObligations(answers, entity, effectiveEntity);
  if (transparencyIds.length) {
    obligationIds.push(...transparencyIds);
    path.push("r4:transparency");
    if (!isHighRisk) {
      const nonLiteracy = obligationIds.filter((id) => id !== "ai_literacy");
      if (nonLiteracy.every((id) => id.startsWith("transparency"))) {
        statusIds.push("transparency_only");
      }
    }
  }

  // FRIA for deployers
  if (
    answerBool(answers, "r5_fria") &&
    isHighRisk &&
    // Art. 27 applies to Art. 6(2) (Annex III) systems only.
    answerBool(answers, "hr2_annex_iii") &&
    effectiveEntity === "deployer"
  ) {
    obligationIds.push("fria");
    path.push("r5:fria");
  }

  return buildResult({
    in_scope: true,
    path,
    statusIds: dedupeIds(statusIds),
    obligationIds,
    is_high_risk: isHighRisk,
    effective_entity: effectiveEntity,
    answers,
    obligation_basis: Object.fromEntries(
      obligationIds.map((id) => [id, basis(id, answers, entity, effectiveEntity)])
    ),
  });
}

// Art. 50 items: answer value, obligation id, role that carries the duty.
const TRANSPARENCY_ITEMS: [string, string, "provider" | "deployer"][] = [
  ["interaction", "transparency_interaction", "provider"],
  ["synthetic_content", "transparency_synthetic", "provider"],
  ["emotion_biometric", "transparency_emotion_biometric", "deployer"],
  ["deepfake", "transparency_deepfake", "deployer"],
  ["public_interest_text", "transparency_public_text", "deployer"],
];

/** Art. 50 obligations, per item and role when r4_transparency_items is given. */
function transparencyObligations(
  answers: Record<string, unknown>,
  entity: EntityType,
  effectiveEntity: EntityType
): string[] {
  const items = answers["r4_transparency_items"];
  if (!Array.isArray(items)) {
    return answerBool(answers, "r4_transparency") ? ["transparency"] : [];
  }
  const isProvider =
    effectiveEntity === "provider" || entity === "product_manufacturer";
  const isDeployer = entity === "deployer";
  return TRANSPARENCY_ITEMS.filter(
    (item) =>
      items.includes(item[0]) && (item[2] === "provider" ? isProvider : isDeployer)
  ).map((item) => item[1]);
}

const ART_6_3_KEYS = [
  "hr3_art_6_3",
  "hr4_narrow_task",
  "hr5_no_significant_risk",
  "hr6_accessory",
];

/** Answer keys that made an obligation apply. Scope gates are left out. */
function basis(
  obligationId: string,
  answers: Record<string, unknown>,
  entity: EntityType,
  effectiveEntity: EntityType
): string[] {
  const role = ["e1_entity_type"];
  if (effectiveEntity !== entity) role.push("e2_modifications");
  if (entity === "product_manufacturer") role.push("e3_product_integration");
  const annexI =
    answerBool(answers, "hr1_annex_i") &&
    answerBool(answers, "hr8_conformity_assessment");
  const high = annexI ? ["hr1_annex_i", "hr8_conformity_assessment"] : [];
  if (answerBool(answers, "hr2_annex_iii")) {
    high.push("hr2_annex_iii", "hr7_profiling");
    if (!annexI && !answerBool(answers, "hr7_profiling")) high.push(...ART_6_3_KEYS);
  }
  if (obligationId === "gpai_provider") return ["s1_gpai"];
  if (obligationId === "gpai_systemic_risk") return ["s1_gpai", "s1_gpai_systemic_risk"];
  if (obligationId === "transparency") return ["r4_transparency"];
  if (obligationId.startsWith("transparency_")) return [...role, "r4_transparency_items"];
  if (obligationId === "ai_literacy" || obligationId === "product_manufacturer") return role;
  if (obligationId === "provider_art_6_4_registration") {
    return [...role, "hr2_annex_iii", "hr7_profiling", ...ART_6_3_KEYS];
  }
  if (obligationId === "fria") return [...role, ...high, "r5_fria"];
  return [...role, ...high];
}
