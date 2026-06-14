/**
 * TypeScript port of packages/core/src/opencomplai_core/compliance_checker/engine.py
 * Deterministic FLI-parity compliance checker — checker version fli-2025-07-28.
 *
 * Must produce identical output to the Python evaluate() for all 17 golden
 * fixtures in packages/core/tests/fixtures/fli_golden/.
 */
import {
  getObligation,
  getStatusChange,
  ObligationItem,
  StatusChangeItem,
} from "./catalog";

export const CHECKER_VERSION = "fli-2025-07-28";

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
  const hr1 = answerBool(answers, "hr1_annex_i");
  const hr2 = answerBool(answers, "hr2_annex_iii");
  if (!hr1 && !hr2) return false;
  if (answerBool(answers, "hr3_art_6_3")) return false;
  if (answerBool(answers, "hr4_narrow_task")) return false;
  if (answerBool(answers, "hr5_no_significant_risk")) return false;
  if (answerBool(answers, "hr6_accessory")) return false;
  return true;
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
    if (isHighRisk) ids.push("deployer_high_risk", "deployer_general");
    else ids.push("deployer_general");
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
    });
  }

  // AI literacy for provider + deployer
  if (effectiveEntity === "provider" || effectiveEntity === "deployer") {
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

  // Transparency (limited-risk only)
  if (answerBool(answers, "r4_transparency") && !isHighRisk) {
    obligationIds.push("transparency");
    path.push("r4:transparency");
    const nonLiteracy = obligationIds.filter((id) => id !== "ai_literacy");
    if (
      (obligationIds.length === 2 &&
        obligationIds[0] === "ai_literacy" &&
        obligationIds[1] === "transparency") ||
      (nonLiteracy.length === 1 && nonLiteracy[0] === "transparency")
    ) {
      statusIds.push("transparency_only");
    }
  }

  // FRIA for deployers
  if (
    answerBool(answers, "r5_fria") &&
    isHighRisk &&
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
  });
}
