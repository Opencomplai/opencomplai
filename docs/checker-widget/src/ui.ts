/**
 * Wizard UI — renders the full EU AI Act applicability questionnaire into
 * #ococ-checker, inheriting the MkDocs Material CSS custom properties for
 * automatic light/dark and brand-colour support. Zero external dependencies.
 *
 * Interaction model:
 *   - confirm  → two buttons (Yes / No); clicking answers and auto-advances.
 *   - select   → option cards (radio semantics); clicking answers and auto-advances.
 *   - multi    → toggleable option cards + an explicit Next button.
 * A Back button is shown on every step except the first. Changing an earlier
 * answer prunes now-stale downstream answers so the result can't be contaminated
 * by an abandoned branch.
 */
import { evaluate, CHECKER_VERSION, CheckerResult } from "./engine";
import { HELP_CONTENT, ENTITY_ROLES } from "./catalog";

const DISCLAIMER =
  "This tool automates EU AI Act compliance checker logic " +
  "for educational and planning purposes. It does not constitute legal advice. " +
  "Seek qualified legal counsel and follow national guidance for formal compliance decisions.";

const PRIVACY_NOTE =
  "🔒 Runs entirely in your browser. Your answers are never transmitted.";

// ── question definitions (mirrors run_interactive_wizard in checker.py) ───────

type QuestionType = "confirm" | "select" | "multi";

interface SelectOption {
  value: string;
  label: string;
  description?: string;
}

interface Question {
  key: string;
  label: string;
  type: QuestionType;
  /** short uppercase eyebrow grouping the question into a phase */
  section?: string;
  options?: SelectOption[];
  helpKey?: string;
  defaultBool?: boolean;
  /** return true to skip this question given current answers */
  skip?: (answers: Record<string, unknown>) => boolean;
}

// Operator-role options come from the shared catalog (help_content.json) so the
// CLI wizard and this widget present identical definitions. Fixed display order.
const ENTITY_ORDER = [
  "provider",
  "deployer",
  "distributor",
  "importer",
  "product_manufacturer",
  "authorised_rep",
];

const ENTITY_FALLBACK: Record<string, string> = {
  provider: "Provider",
  deployer: "Deployer",
  distributor: "Distributor",
  importer: "Importer",
  product_manufacturer: "Product manufacturer",
  authorised_rep: "Authorised representative",
};

const ENTITY_OPTIONS: SelectOption[] = ENTITY_ORDER.map((value) => ({
  value,
  label: ENTITY_ROLES[value]?.title ?? ENTITY_FALLBACK[value] ?? value,
  description: ENTITY_ROLES[value]?.description,
}));

const QUESTIONS: Question[] = [
  {
    key: "gate_is_ai_system",
    label: "Is this an AI system under Article 3(1)?",
    type: "confirm",
    section: "AI system",
    defaultBool: true,
    helpKey: "ai_system_definition",
  },
  {
    key: "e1_entity_type",
    label: "Which kind of entity is your organisation?",
    type: "select",
    section: "Operator role",
    options: ENTITY_OPTIONS,
    helpKey: "entity_definitions",
    skip: (a) => a["gate_is_ai_system"] === false,
  },
  {
    key: "e2_modifications",
    label: "Do you (or a downstream operator) make substantial modifications to the system?",
    type: "confirm",
    section: "Operator role",
    defaultBool: false,
    helpKey: "modifications_overview",
    skip: (a) =>
      !a["gate_is_ai_system"] ||
      a["e1_entity_type"] === "authorised_rep" ||
      a["e1_entity_type"] === "product_manufacturer",
  },
  {
    key: "e3_product_integration",
    label: "Does your product integrate an AI system placed on the market under your name?",
    type: "select",
    section: "Operator role",
    options: [
      {
        value: "integrated",
        label: "Yes — placed on market under my name / trademark",
        description: "The AI system ships as part of your product, under your brand.",
      },
      {
        value: "none",
        label: "No",
        description: "Your product does not place an AI system on the market under your name.",
      },
    ],
    skip: (a) => a["e1_entity_type"] !== "product_manufacturer",
  },
  {
    key: "hr1_annex_i",
    label: "Is the system a product with AI as a safety component under Annex I harmonisation law?",
    type: "confirm",
    section: "Risk classification",
    defaultBool: false,
    helpKey: "high_risk_overview",
    skip: (a) =>
      !a["gate_is_ai_system"] ||
      a["e1_entity_type"] === "authorised_rep" ||
      (a["e1_entity_type"] === "product_manufacturer" &&
        a["e3_product_integration"] === "none"),
  },
  {
    key: "hr2_annex_iii",
    label: "Does the system fall within an Annex III high-risk use case?",
    type: "confirm",
    section: "Risk classification",
    defaultBool: false,
    helpKey: "high_risk_overview",
    skip: (a) =>
      !a["gate_is_ai_system"] ||
      a["e1_entity_type"] === "authorised_rep" ||
      (a["e1_entity_type"] === "product_manufacturer" &&
        a["e3_product_integration"] === "none"),
  },
  {
    key: "hr3_art_6_3",
    label: "Does Article 6(3) apply (safety component required for product conformity)?",
    type: "confirm",
    section: "Risk classification",
    defaultBool: false,
    skip: (a) => !a["hr1_annex_i"] && !a["hr2_annex_iii"],
  },
  {
    key: "hr4_narrow_task",
    label: "Is the AI intended only for a narrow procedural task (Art 6(3) exception)?",
    type: "confirm",
    section: "Risk classification",
    defaultBool: false,
    skip: (a) => !a["hr1_annex_i"] && !a["hr2_annex_iii"],
  },
  {
    key: "hr5_no_significant_risk",
    label: "Does the system NOT pose significant risk to health, safety, or fundamental rights?",
    type: "confirm",
    section: "Risk classification",
    defaultBool: false,
    skip: (a) => !a["hr1_annex_i"] && !a["hr2_annex_iii"],
  },
  {
    key: "hr6_accessory",
    label: "Is the system purely accessory to the relevant human decision (Art 6(3))?",
    type: "confirm",
    section: "Risk classification",
    defaultBool: false,
    skip: (a) => !a["hr1_annex_i"] && !a["hr2_annex_iii"],
  },
  {
    key: "s1_in_scope",
    label: "Are you placing, deploying, or using the system's output in the EU?",
    type: "confirm",
    section: "Scope",
    defaultBool: true,
    helpKey: "scope_overview",
    skip: (a) =>
      !a["gate_is_ai_system"] ||
      a["e1_entity_type"] === "authorised_rep" ||
      (a["e1_entity_type"] === "product_manufacturer" &&
        a["e3_product_integration"] === "none"),
  },
  {
    key: "s1_scope_region",
    label: "Where is your organisation established?",
    type: "select",
    section: "Scope",
    options: [
      {
        value: "eu",
        label: "Established or located in the EU",
        description: "Your organisation has a place of establishment inside the Union.",
      },
      {
        value: "third_country",
        label: "Outside the EU",
        description: "Your organisation is established in a third country.",
      },
    ],
    skip: (a) => !a["s1_in_scope"],
  },
  {
    key: "s1_gpai",
    label: "Are you placing a General-Purpose AI model on the EU market?",
    type: "confirm",
    section: "Scope",
    defaultBool: false,
    helpKey: "gpai_overview",
    skip: (a) => !a["s1_in_scope"],
  },
  {
    key: "s1_gpai_systemic_risk",
    label: "Does the GPAI model have systemic risk (high-impact capabilities)?",
    type: "confirm",
    section: "Scope",
    defaultBool: false,
    skip: (a) => !a["s1_gpai"],
  },
  {
    key: "r2_excluded",
    label:
      "Is the system excluded (military, R&D only, open-source not yet placed, personal use)?",
    type: "confirm",
    section: "Scope",
    defaultBool: false,
    skip: (a) => !a["s1_in_scope"],
  },
  {
    key: "r3_prohibited",
    label: "Does the system perform prohibited practices under Article 5?",
    type: "confirm",
    section: "Obligations",
    defaultBool: false,
    skip: (a) => !a["s1_in_scope"] || !!a["r2_excluded"],
  },
  {
    key: "r4_transparency",
    label:
      "Does the system require transparency obligations (chatbot, deepfake, synthetic content)?",
    type: "confirm",
    section: "Obligations",
    defaultBool: false,
    skip: (a) =>
      !a["s1_in_scope"] || !!a["r2_excluded"] || !!a["r3_prohibited"],
  },
  {
    key: "r5_fria",
    label:
      "Are you a public body or private entity providing public services? (FRIA under Art 27)",
    type: "confirm",
    section: "Obligations",
    defaultBool: false,
    skip: (a) =>
      !a["s1_in_scope"] ||
      !!a["r2_excluded"] ||
      !!a["r3_prohibited"] ||
      a["e1_entity_type"] !== "deployer",
  },
];

// ── CSS (brand tokens with Material-var fallback for light/dark parity) ──────

const CSS = `
#ococ-checker {
  --ococ-accent: var(--color-electric-blue, var(--md-primary-fg-color, #3B5BEB));
  --ococ-accent-dark: var(--color-primary-dark, var(--md-primary-fg-color--dark, #2d46c7));
  --ococ-accent-soft: var(--ococ-accent-soft-override, rgba(59, 91, 235, 0.08));
  --ococ-ink: var(--color-midnight, var(--md-default-fg-color, #21283B));
  --ococ-ink-muted: var(--color-fg-muted, var(--md-default-fg-color--light, #5a6478));
  --ococ-surface: var(--md-default-bg-color, #fff);
  --ococ-surface-subtle: var(--color-cool-gray, var(--md-default-fg-color--lightest, #F1F4F8));
  --ococ-border: var(--color-border, var(--md-default-fg-color--lightest, #e2e6ed));
  --ococ-success: var(--color-success-green, #12D463);
  --ococ-success-soft: rgba(18, 212, 99, 0.10);
  --ococ-danger: #d1293d;
  --ococ-danger-soft: rgba(209, 41, 61, 0.09);
  --ococ-warning: #b3690a;
  --ococ-warning-soft: rgba(217, 138, 15, 0.12);
  font-family: var(--font-sans, var(--md-text-font, system-ui, sans-serif));
  max-width: 720px;
  margin: 0 auto;
}
[data-md-color-scheme="slate"] #ococ-checker {
  --ococ-accent-soft-override: rgba(92, 120, 240, 0.16);
  --ococ-surface-subtle: var(--md-default-fg-color--lightest, #2a3142);
  --ococ-border: var(--md-default-fg-color--lightest, #333c50);
  --ococ-success-soft: rgba(18, 212, 99, 0.14);
  --ococ-danger-soft: rgba(255, 99, 118, 0.14);
  --ococ-warning-soft: rgba(245, 166, 35, 0.16);
}

.ococ-frame { display: flex; flex-direction: column; gap: 0.9rem; }

/* ── status rail: step counter + progress track, outside the card ── */
.ococ-rail {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 1rem;
}
.ococ-rail-label {
  font-size: 0.72rem;
  font-weight: 600;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  color: var(--ococ-ink-muted);
}
.ococ-rail-count {
  font-size: 0.72rem;
  font-weight: 600;
  font-variant-numeric: tabular-nums;
  color: var(--ococ-accent);
  letter-spacing: 0.02em;
}
.ococ-progress-track {
  height: 4px;
  border-radius: 2px;
  background: var(--ococ-border);
  overflow: hidden;
}
.ococ-progress-fill {
  height: 100%;
  border-radius: 2px;
  background: var(--ococ-accent);
  transition: width 0.35s cubic-bezier(0.4, 0, 0.2, 1);
}

.ococ-card {
  border: 1px solid var(--ococ-border);
  border-radius: 14px;
  padding: 1.75rem 2rem;
  background: var(--ococ-surface);
  box-shadow: 0 1px 2px rgba(33, 40, 59, 0.04), 0 12px 28px rgba(33, 40, 59, 0.06);
}
[data-md-color-scheme="slate"] .ococ-card {
  box-shadow: 0 1px 2px rgba(0,0,0,0.2), 0 12px 28px rgba(0,0,0,0.28);
}

.ococ-eyebrow {
  font-size: 0.72rem;
  font-weight: 700;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: var(--ococ-accent);
  margin-bottom: 0.6rem;
}
.ococ-question {
  font-size: 1.32rem;
  font-weight: 650;
  line-height: 1.32;
  letter-spacing: -0.01em;
  margin-bottom: 1rem;
  color: var(--ococ-ink);
}
.ococ-help details {
  margin-bottom: 1.1rem;
  font-size: 0.88rem;
  color: var(--ococ-ink-muted);
}
.ococ-help summary {
  cursor: pointer;
  color: var(--ococ-accent);
  font-weight: 600;
  list-style: none;
  display: inline-flex;
  align-items: center;
  gap: 0.35rem;
}
.ococ-help summary::before { content: "ⓘ"; }
.ococ-help summary::-webkit-details-marker { display: none; }
.ococ-help p {
  margin: 0.6rem 0 0;
  line-height: 1.55;
  padding: 0.75rem 0.9rem;
  background: var(--ococ-surface-subtle);
  border-radius: 8px;
  border-left: 2.5px solid var(--ococ-accent);
}

/* option list (select + multi) */
.ococ-options { display: flex; flex-direction: column; gap: 0.6rem; }
.ococ-option {
  display: flex;
  align-items: flex-start;
  gap: 0.85rem;
  width: 100%;
  text-align: left;
  padding: 0.95rem 1.1rem;
  border: 1.5px solid var(--ococ-border);
  border-radius: 10px;
  background: var(--ococ-surface);
  color: var(--ococ-ink);
  cursor: pointer;
  font: inherit;
  transition: border-color 0.15s, background 0.15s, box-shadow 0.15s, transform 0.05s;
}
.ococ-option:hover {
  border-color: var(--ococ-accent);
  box-shadow: 0 2px 8px rgba(59, 91, 235, 0.10);
}
.ococ-option:active { transform: translateY(1px); }
.ococ-option[aria-checked="true"] {
  border-color: var(--ococ-accent);
  background: var(--ococ-accent-soft);
  box-shadow: inset 0 0 0 1.5px var(--ococ-accent);
}
.ococ-option-marker {
  flex: 0 0 auto;
  width: 20px;
  height: 20px;
  margin-top: 1px;
  border-radius: 50%;
  border: 2px solid var(--ococ-border);
  display: grid;
  place-items: center;
  transition: border-color 0.15s, background 0.15s;
}
.ococ-option--multi .ococ-option-marker { border-radius: 5px; }
.ococ-option[aria-checked="true"] .ococ-option-marker {
  border-color: var(--ococ-accent);
  background: var(--ococ-accent);
}
.ococ-option-marker svg { width: 12px; height: 12px; display: none; }
.ococ-option[aria-checked="true"] .ococ-option-marker svg { display: block; }
.ococ-option-body { display: flex; flex-direction: column; gap: 0.2rem; }
.ococ-option-title { font-weight: 600; font-size: 0.98rem; color: var(--ococ-ink); }
.ococ-option-desc {
  font-size: 0.84rem;
  line-height: 1.5;
  color: var(--ococ-ink-muted);
}

/* yes / no */
.ococ-yesno { display: flex; gap: 0.75rem; }
.ococ-yesno .ococ-option { flex: 1 1 0; justify-content: center; align-items: center; font-weight: 600; font-size: 1.05rem; padding: 1.1rem; }
.ococ-yesno .ococ-option-body { align-items: center; }

/* navigation */
.ococ-actions {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  margin-top: 1.75rem;
  padding-top: 1.5rem;
  border-top: 1px solid var(--ococ-border);
  flex-wrap: wrap;
}
.ococ-spacer { flex: 1 1 auto; }
.ococ-btn {
  padding: 0.65rem 1.35rem;
  border-radius: 8px;
  border: 1.5px solid transparent;
  cursor: pointer;
  font-size: 0.9rem;
  font-weight: 600;
  font-family: inherit;
  transition: background 0.15s, border-color 0.15s, color 0.15s, transform 0.05s;
}
.ococ-btn:active { transform: translateY(1px); }
.ococ-btn-primary { background: var(--ococ-accent); color: #fff; }
.ococ-btn-primary:hover { background: var(--ococ-accent-dark); }
.ococ-btn-secondary {
  background: transparent;
  border-color: var(--ococ-border);
  color: var(--ococ-ink-muted);
}
.ococ-btn-secondary:hover {
  border-color: var(--ococ-ink-muted);
  color: var(--ococ-ink);
}
.ococ-btn:disabled { opacity: 0.4; cursor: default; }

/* focus visibility (keyboard) */
.ococ-option:focus-visible,
.ococ-btn:focus-visible,
.ococ-help summary:focus-visible {
  outline: 2px solid var(--ococ-accent);
  outline-offset: 2px;
}

/* ── result ── */
.ococ-result-banner {
  display: flex;
  align-items: flex-start;
  gap: 0.9rem;
  padding: 1.1rem 1.25rem;
  border-radius: 10px;
  margin-bottom: 1.5rem;
  border-left: 4px solid transparent;
}
.ococ-result-banner-icon {
  flex: 0 0 auto;
  width: 26px;
  height: 26px;
  display: grid;
  place-items: center;
  margin-top: 0.1rem;
}
.ococ-result-banner-icon svg { width: 22px; height: 22px; }
.ococ-result-banner-text { display: flex; flex-direction: column; gap: 0.15rem; }
.ococ-result-headline { font-size: 1.18rem; font-weight: 700; line-height: 1.3; }
.ococ-result-sub { font-size: 0.86rem; font-weight: 500; opacity: 0.85; }

.ococ-result-prohibited { background: var(--ococ-danger-soft); border-left-color: var(--ococ-danger); color: var(--ococ-danger); }
.ococ-result-high { background: var(--ococ-warning-soft); border-left-color: var(--ococ-warning); color: var(--ococ-warning); }
.ococ-result-in-scope { background: var(--ococ-success-soft); border-left-color: var(--ococ-success); color: #0a8f4c; }
[data-md-color-scheme="slate"] .ococ-result-in-scope { color: #34e08c; }
.ococ-result-out { background: var(--ococ-surface-subtle); border-left-color: var(--ococ-ink-muted); color: var(--ococ-ink-muted); }

.ococ-section-title {
  font-size: 0.78rem;
  font-weight: 700;
  margin: 1.5rem 0 0.6rem;
  text-transform: uppercase;
  letter-spacing: 0.06em;
  color: var(--ococ-ink-muted);
}
.ococ-table { width: 100%; border-collapse: collapse; font-size: 0.88rem; margin-bottom: 0.5rem; font-variant-numeric: tabular-nums; }
.ococ-table th {
  text-align: left; padding: 0.55rem 0.7rem;
  background: var(--ococ-surface-subtle);
  font-weight: 600; color: var(--ococ-ink);
}
.ococ-table th:first-child { border-radius: 6px 0 0 6px; }
.ococ-table th:last-child { border-radius: 0 6px 6px 0; }
.ococ-table td {
  padding: 0.6rem 0.7rem;
  border-top: 1px solid var(--ococ-border);
  vertical-align: top; color: var(--ococ-ink);
}
.ococ-path details { font-size: 0.82rem; margin-top: 0.75rem; }
.ococ-path summary { cursor: pointer; color: var(--ococ-ink-muted); font-weight: 500; }
.ococ-path code {
  display: inline-block; background: var(--ococ-surface-subtle);
  border-radius: 4px; padding: 0.1rem 0.45rem; font-size: 0.8rem; margin: 0.15rem 0.1rem 0 0;
  color: var(--ococ-ink); font-family: var(--font-mono, ui-monospace, monospace);
}
.ococ-export { display: flex; gap: 0.5rem; flex-wrap: wrap; margin-top: 0.75rem; }
.ococ-disclaimer {
  font-size: 0.78rem; color: var(--ococ-ink-muted);
  margin-top: 1.5rem; padding-top: 1rem;
  border-top: 1px solid var(--ococ-border);
  line-height: 1.55;
}
.ococ-privacy {
  display: flex;
  align-items: center;
  gap: 0.4rem;
  font-size: 0.82rem;
  color: var(--ococ-ink-muted);
  margin: 0 0 1.25rem;
}

.ococ-local-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.75rem;
  font-size: 0.78rem;
  color: var(--ococ-ink-muted);
  background: var(--ococ-surface-subtle);
  border: 1px solid var(--ococ-border);
  border-radius: 8px;
  padding: 0.5rem 0.75rem;
}
.ococ-answer-row {
  display: flex;
  justify-content: space-between;
  gap: 1rem;
  font-size: 0.86rem;
  padding: 0.35rem 0;
  border-bottom: 1px solid var(--ococ-border);
}
.ococ-answer-row:last-child { border-bottom: none; }
.ococ-answer-row .ococ-answer-label { color: var(--ococ-ink-muted); }
.ococ-answer-row .ococ-answer-value { color: var(--ococ-ink); font-weight: 600; text-align: right; }
.ococ-email {
  display: flex;
  gap: 0.5rem;
  flex-wrap: wrap;
  margin-top: 0.75rem;
  align-items: center;
}
.ococ-email input[type="email"] {
  flex: 1 1 220px;
  min-width: 0;
  padding: 0.5rem 0.7rem;
  border-radius: 8px;
  border: 1px solid var(--ococ-border);
  background: var(--ococ-surface);
  color: var(--ococ-ink);
  font-size: 0.88rem;
}
.ococ-email-status { font-size: 0.82rem; color: var(--ococ-ink-muted); margin-top: 0.4rem; }
.ococ-email-status.ococ-email-error { color: var(--ococ-danger); }
.ococ-email-status.ococ-email-success { color: var(--ococ-success); }

@media (max-width: 520px) {
  .ococ-card { padding: 1.35rem 1.25rem; }
  .ococ-yesno { flex-direction: column; }
}
@media (prefers-reduced-motion: reduce) {
  .ococ-progress-fill, .ococ-option, .ococ-btn { transition: none; }
}
`;

function injectStyles() {
  if (document.getElementById("ococ-styles")) return;
  const el = document.createElement("style");
  el.id = "ococ-styles";
  el.textContent = CSS;
  document.head.appendChild(el);
}

// ── state ─────────────────────────────────────────────────────────────────────

interface State {
  step: number;
  answers: Record<string, unknown>;
  result: CheckerResult | null;
}

// ── active question list (skipping inapplicable questions) ────────────────────

function activeQuestions(answers: Record<string, unknown>): Question[] {
  return QUESTIONS.filter((q) => !q.skip?.(answers));
}

// ── answer mutation with stale-branch pruning ─────────────────────────────────

function valuesEqual(a: unknown, b: unknown): boolean {
  if (Array.isArray(a) && Array.isArray(b)) {
    return a.length === b.length && a.every((v, i) => v === b[i]);
  }
  return a === b;
}

/** Clear answers for every question after `key` in the canonical flow. */
function pruneAfter(answers: Record<string, unknown>, key: string): void {
  const idx = QUESTIONS.findIndex((q) => q.key === key);
  if (idx < 0) return;
  for (let i = idx + 1; i < QUESTIONS.length; i++) {
    delete answers[QUESTIONS[i].key];
  }
}

/** Set an answer; if it changed, prune now-stale downstream answers. */
function setAnswer(state: State, q: Question, value: unknown): void {
  const changed = !valuesEqual(state.answers[q.key], value);
  state.answers[q.key] = value;
  if (changed) pruneAfter(state.answers, q.key);
}

// ── rendering ─────────────────────────────────────────────────────────────────

function h(tag: string, attrs: Record<string, string> = {}, ...children: (string | Node)[]): HTMLElement {
  const el = document.createElement(tag);
  for (const entry of Object.entries(attrs)) {
    const k = entry[0];
    const v = entry[1];
    if (k === "className") el.className = v;
    else el.setAttribute(k, v);
  }
  for (const child of children) {
    if (typeof child === "string") el.appendChild(document.createTextNode(child));
    else el.appendChild(child);
  }
  return el;
}

const CHECK_SVG =
  '<svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">' +
  '<path d="M20 6L9 17l-5-5" stroke="#fff" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"/></svg>';

function makeOption(opts: {
  title: string;
  description?: string;
  checked: boolean;
  multi: boolean;
}): HTMLButtonElement {
  const btn = document.createElement("button");
  btn.type = "button";
  btn.className = "ococ-option" + (opts.multi ? " ococ-option--multi" : "");
  btn.setAttribute("role", opts.multi ? "checkbox" : "radio");
  btn.setAttribute("aria-checked", String(opts.checked));

  const marker = h("span", { className: "ococ-option-marker" });
  marker.innerHTML = CHECK_SVG;
  btn.appendChild(marker);

  const body = h("span", { className: "ococ-option-body" });
  body.appendChild(h("span", { className: "ococ-option-title" }, opts.title));
  if (opts.description) {
    body.appendChild(h("span", { className: "ococ-option-desc" }, opts.description));
  }
  btn.appendChild(body);
  return btn;
}

/** Move keyboard focus between options with the arrow keys. */
function wireArrowNav(group: HTMLElement): void {
  group.addEventListener("keydown", (ev: KeyboardEvent) => {
    if (ev.key !== "ArrowDown" && ev.key !== "ArrowUp") return;
    const items = Array.from(group.querySelectorAll<HTMLButtonElement>(".ococ-option"));
    const current = document.activeElement as HTMLElement;
    const idx = items.indexOf(current as HTMLButtonElement);
    if (idx < 0) return;
    ev.preventDefault();
    const delta = ev.key === "ArrowDown" ? 1 : -1;
    const next = items[(idx + delta + items.length) % items.length];
    next.focus();
  });
}

function renderQuestion(state: State, root: HTMLElement) {
  const questions = activeQuestions(state.answers);

  // Branch logic may have shortened the flow — clamp to results.
  if (state.step >= questions.length) {
    state.result = evaluate(state.answers);
    renderResult(state, root);
    return;
  }

  const q = questions[state.step];
  const total = questions.length;
  const pct = Math.round(((state.step + 1) / total) * 100);

  root.innerHTML = "";
  const frame = h("div", { className: "ococ-frame" });
  appendLocalServerControl(frame);

  const rail = h("div", { className: "ococ-rail" });
  rail.appendChild(h("span", { className: "ococ-rail-label" }, q.section ?? "EU AI Act Checker"));
  rail.appendChild(h("span", { className: "ococ-rail-count" }, `Step ${state.step + 1} of ${total}`));
  frame.appendChild(rail);

  const track = h("div", { className: "ococ-progress-track" });
  const fill = h("div", { className: "ococ-progress-fill" });
  fill.style.width = `${pct}%`;
  track.appendChild(fill);
  frame.appendChild(track);

  const card = h("div", { className: "ococ-card" });

  if (state.step === 0) {
    card.appendChild(h("p", { className: "ococ-privacy" }, PRIVACY_NOTE));
  }

  if (q.section) {
    card.appendChild(h("div", { className: "ococ-eyebrow" }, q.section));
  }

  card.appendChild(h("div", { className: "ococ-question" }, q.label));

  if (q.helpKey) {
    const section = HELP_CONTENT[q.helpKey];
    if (section) {
      const helpDiv = h("div", { className: "ococ-help" });
      const details = document.createElement("details");
      details.appendChild(h("summary", {}, "Learn more"));
      const body = h("p", {});
      body.textContent = section.body;
      details.appendChild(body);
      helpDiv.appendChild(details);
      card.appendChild(helpDiv);
    }
  }

  const currentVal = state.answers[q.key];
  const advance = () => goNext(state, root, q.key);

  if (q.type === "confirm") {
    const group = h("div", { className: "ococ-options ococ-yesno" });
    const yes = makeOption({ title: "Yes", checked: currentVal === true, multi: false });
    const no = makeOption({ title: "No", checked: currentVal === false, multi: false });
    yes.onclick = () => { setAnswer(state, q, true); advance(); };
    no.onclick = () => { setAnswer(state, q, false); advance(); };
    group.appendChild(yes);
    group.appendChild(no);
    wireArrowNav(group);
    card.appendChild(group);
  } else if (q.type === "select" && q.options) {
    const group = h("div", { className: "ococ-options", role: "radiogroup" });
    group.setAttribute("aria-label", q.label);
    for (const opt of q.options) {
      const btn = makeOption({
        title: opt.label,
        description: opt.description,
        checked: currentVal === opt.value,
        multi: false,
      });
      btn.onclick = () => { setAnswer(state, q, opt.value); advance(); };
      group.appendChild(btn);
    }
    wireArrowNav(group);
    card.appendChild(group);
  } else if (q.type === "multi" && q.options) {
    const selected = new Set(Array.isArray(currentVal) ? (currentVal as string[]) : []);
    const group = h("div", { className: "ococ-options", role: "group" });
    group.setAttribute("aria-label", q.label);
    for (const opt of q.options) {
      const btn = makeOption({
        title: opt.label,
        description: opt.description,
        checked: selected.has(opt.value),
        multi: true,
      });
      btn.onclick = () => {
        if (selected.has(opt.value)) selected.delete(opt.value);
        else selected.add(opt.value);
        btn.setAttribute("aria-checked", String(selected.has(opt.value)));
        // store without pruning until the user commits with Next
        state.answers[q.key] = [...selected];
      };
      group.appendChild(btn);
    }
    wireArrowNav(group);
    card.appendChild(group);
  }

  // ── navigation row ──
  const actions = h("div", { className: "ococ-actions" });
  if (state.step > 0) {
    const back = h("button", { className: "ococ-btn ococ-btn-secondary", type: "button" }, "← Back");
    (back as HTMLButtonElement).onclick = () => goBack(state, root);
    actions.appendChild(back);
  }
  // multi-select needs an explicit commit; confirm/select auto-advance on click.
  if (q.type === "multi") {
    actions.appendChild(h("span", { className: "ococ-spacer" }));
    const isLast = state.step >= questions.length - 1;
    const next = h("button", { className: "ococ-btn ococ-btn-primary", type: "button" },
      isLast ? "See results →" : "Next →");
    (next as HTMLButtonElement).onclick = () => {
      // ensure the array is committed and prune any stale downstream answers
      setAnswer(state, q, [...(Array.isArray(state.answers[q.key]) ? (state.answers[q.key] as string[]) : [])]);
      advance();
    };
    actions.appendChild(next);
  }
  card.appendChild(actions);

  card.appendChild(h("p", { className: "ococ-disclaimer" }, DISCLAIMER));
  frame.appendChild(card);
  root.appendChild(frame);

  // Move focus to the answer group for keyboard users (not on the very first paint).
  const firstOption = card.querySelector<HTMLButtonElement>(".ococ-option");
  if (firstOption && state.step > 0) firstOption.focus();
}

function goNext(state: State, root: HTMLElement, currentKey: string) {
  const questions = activeQuestions(state.answers);
  const curIdx = questions.findIndex((q) => q.key === currentKey);
  const nextIdx = (curIdx < 0 ? state.step : curIdx) + 1;
  if (nextIdx >= questions.length) {
    state.result = evaluate(state.answers);
    renderResult(state, root);
    return;
  }
  state.step = nextIdx;
  renderQuestion(state, root);
}

function goBack(state: State, root: HTMLElement) {
  if (state.step > 0) {
    state.step -= 1;
    renderQuestion(state, root);
  }
}

function headlineClass(result: CheckerResult): string {
  if (result.is_prohibited) return "ococ-result-prohibited";
  if (result.is_high_risk) return "ococ-result-high";
  if (result.in_scope) return "ococ-result-in-scope";
  return "ococ-result-out";
}

function headlineText(result: CheckerResult): string {
  if (result.is_prohibited) return "Prohibited practice";
  if (result.is_high_risk) return "High risk";
  if (result.in_scope) return "In scope";
  return "Out of scope";
}

function headlineSub(result: CheckerResult): string {
  const role = result.effective_entity
    ? result.effective_entity.replace(/_/g, " ")
    : null;
  if (result.is_prohibited) return "This system may not be placed on the market or put into service.";
  if (result.is_high_risk) {
    return role ? `High-risk obligations apply to you as ${role}.` : "High-risk obligations apply under the AI Act.";
  }
  if (result.in_scope) {
    return role ? `The AI Act applies to you as ${role}.` : "The AI Act applies to this system.";
  }
  return "The AI Act does not apply to this system as described.";
}

const RESULT_ICONS: Record<string, string> = {
  "ococ-result-prohibited":
    '<svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">' +
    '<circle cx="12" cy="12" r="9" stroke="currentColor" stroke-width="2"/>' +
    '<path d="M6 6l12 12" stroke="currentColor" stroke-width="2" stroke-linecap="round"/></svg>',
  "ococ-result-high":
    '<svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">' +
    '<path d="M12 3.5l9.5 16.5H2.5L12 3.5z" stroke="currentColor" stroke-width="2" stroke-linejoin="round"/>' +
    '<path d="M12 10v4" stroke="currentColor" stroke-width="2" stroke-linecap="round"/>' +
    '<circle cx="12" cy="17.2" r="0.9" fill="currentColor"/></svg>',
  "ococ-result-in-scope":
    '<svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">' +
    '<circle cx="12" cy="12" r="9" stroke="currentColor" stroke-width="2"/>' +
    '<path d="M8 12.5l2.5 2.5L16 9.5" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/></svg>',
  "ococ-result-out":
    '<svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">' +
    '<circle cx="12" cy="12" r="9" stroke="currentColor" stroke-width="2"/>' +
    '<path d="M12 8v5" stroke="currentColor" stroke-width="2" stroke-linecap="round"/>' +
    '<circle cx="12" cy="16" r="0.9" fill="currentColor"/></svg>',
};

function downloadFile(filename: string, content: string, mime: string) {
  const blob = new Blob([content], { type: mime });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}

// ── local-CLI stop control ("opencomplai checker --web --local") ────────────
// The CLI marks its served URL with ?local=1 (see _checker_web in main.py) so
// this bundle — otherwise identical whether hosted on docs.opencomplai.com or
// served offline — knows to show a way to stop the local server it's running
// under, instead of requiring the user to find the terminal and press Ctrl+C.

function isLocalCliServed(): boolean {
  return new URLSearchParams(window.location.search).get("local") === "1";
}

function appendLocalServerControl(frame: HTMLElement) {
  if (!isLocalCliServed()) return;
  const bar = h("div", { className: "ococ-local-bar" });
  const label = h("span", {}, "Running locally via opencomplai checker --web --local.");
  const stopBtn = h("button", { className: "ococ-btn ococ-btn-secondary", type: "button" }, "Stop local server");
  (stopBtn as HTMLButtonElement).onclick = () => {
    (stopBtn as HTMLButtonElement).disabled = true;
    stopBtn.textContent = "Stopping…";
    fetch("/__ococ_shutdown", { method: "POST" }).catch(() => {
      // The server closing the connection as it shuts down looks like a
      // failed fetch from here — that's the expected/successful outcome.
    });
    window.setTimeout(() => {
      bar.innerHTML = "";
      bar.appendChild(h("span", {}, "Server stopped — you can close this tab."));
    }, 300);
  };
  bar.appendChild(label);
  bar.appendChild(stopBtn);
  frame.appendChild(bar);
}

// ── answer formatting (mirrors _answer_entries in report.py) ────────────────

function formatAnswerValue(value: unknown, q: Question): string {
  if (typeof value === "boolean") return value ? "Yes" : "No";
  if (Array.isArray(value)) {
    if (!q.options) return value.map(String).join(", ");
    return value
      .map((v) => q.options!.find((o) => o.value === v)?.label ?? String(v))
      .join(", ");
  }
  if (q.options) {
    const opt = q.options.find((o) => o.value === value);
    if (opt) return opt.label;
  }
  if (value === null || value === undefined) return "(no answer)";
  return String(value);
}

interface AnswerEntry {
  section: string;
  label: string;
  value: string;
}

function answerEntries(answers: Record<string, unknown>): AnswerEntry[] {
  const entries: AnswerEntry[] = [];
  const seen = new Set<string>();
  for (const q of QUESTIONS) {
    if (!(q.key in answers)) continue;
    seen.add(q.key);
    entries.push({ section: q.section ?? "", label: q.label, value: formatAnswerValue(answers[q.key], q) });
  }
  for (const key of Object.keys(answers)) {
    if (seen.has(key)) continue;
    const label = key.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
    entries.push({ section: "", label, value: String(answers[key]) });
  }
  return entries;
}

// ── email delivery (public docs site only — see isLocalCliServed) ───────────
// The CLI's --local mode is explicitly offline, so it never shows this; the
// hosted docs.opencomplai.com page calls the risk-engine's /v1/checker/email.

const CHECKER_API_BASE =
  (typeof window !== "undefined" && (window as { OCOC_RISK_ENGINE_URL?: string }).OCOC_RISK_ENGINE_URL) ||
  "http://localhost:8001";

async function emailResult(answers: Record<string, unknown>, toEmail: string): Promise<void> {
  const res = await fetch(`${CHECKER_API_BASE}/v1/checker/email`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ answers, to_email: toEmail }),
  });
  if (!res.ok) {
    let message = "Could not send the email.";
    try {
      const body = await res.json();
      if (body?.detail?.message) message = body.detail.message;
    } catch {
      // non-JSON error body — fall back to the generic message
    }
    throw new Error(message);
  }
}

function renderJson(result: CheckerResult): string {
  // field-identical to Python render_json (minus session_id if null)
  const out: Record<string, unknown> = {
    checker_version: result.checker_version,
    in_scope: result.in_scope,
    is_high_risk: result.is_high_risk,
    is_prohibited: result.is_prohibited,
    effective_entity: result.effective_entity,
    status_changes: result.status_changes,
    obligations: result.obligations,
    determination_path: result.determination_path,
    answers: result.answers,
  };
  if (result.session_id !== null) out["session_id"] = result.session_id;
  return JSON.stringify(out, null, 2);
}

function renderMarkdown(result: CheckerResult): string {
  const lines: string[] = [
    "# EU AI Act Compliance Checker Result",
    "",
    `**Checker version:** ${result.checker_version}`,
    `**In scope:** ${result.in_scope ? "Yes" : "No"}`,
    `**High risk:** ${result.is_high_risk ? "Yes" : "No"}`,
    `**Prohibited:** ${result.is_prohibited ? "Yes" : "No"}`,
  ];
  if (result.effective_entity) {
    lines.push(`**Effective operator role:** ${result.effective_entity}`);
  }

  lines.push("", "## Your answers", "");
  const answers = answerEntries(result.answers);
  if (answers.length) {
    let lastSection = "";
    for (const entry of answers) {
      if (entry.section && entry.section !== lastSection) {
        lines.push(`**${entry.section}**`);
        lastSection = entry.section;
      }
      lines.push(`- ${entry.label} — ${entry.value}`);
    }
  } else {
    lines.push("None.");
  }

  lines.push("", "## Status changes", "");
  if (result.status_changes.length) {
    for (const sc of result.status_changes) {
      lines.push(`### ${sc.title}`, "", sc.body, "");
    }
  } else {
    lines.push("None.", "");
  }
  lines.push("## Obligations", "");
  if (result.obligations.length) {
    for (const ob of result.obligations) {
      lines.push(`### ${ob.title} (${ob.article_ref})`, "", ob.body, "");
    }
  } else {
    lines.push("None.", "");
  }
  lines.push("## Determination path", "");
  for (const step of result.determination_path) {
    lines.push(`- \`${step}\``);
  }
  lines.push("", "## Disclaimer", "", DISCLAIMER, "");
  return lines.join("\n");
}

function renderResult(state: State, root: HTMLElement) {
  const result = state.result!;
  root.innerHTML = "";

  const frame = h("div", { className: "ococ-frame" });
  appendLocalServerControl(frame);

  const rail = h("div", { className: "ococ-rail" });
  rail.appendChild(h("span", { className: "ococ-rail-label" }, "EU AI Act Checker"));
  rail.appendChild(h("span", { className: "ococ-rail-count" }, "Result"));
  frame.appendChild(rail);

  const track = h("div", { className: "ococ-progress-track" });
  const fill = h("div", { className: "ococ-progress-fill" });
  fill.style.width = "100%";
  track.appendChild(fill);
  frame.appendChild(track);

  const card = h("div", { className: "ococ-card" });

  const resultClass = headlineClass(result);
  const banner = h("div", { className: `ococ-result-banner ${resultClass}` });
  const icon = h("span", { className: "ococ-result-banner-icon" });
  icon.innerHTML = RESULT_ICONS[resultClass] ?? "";
  banner.appendChild(icon);
  const bannerText = h("div", { className: "ococ-result-banner-text" });
  bannerText.appendChild(h("div", { className: "ococ-result-headline" }, headlineText(result)));
  bannerText.appendChild(h("div", { className: "ococ-result-sub" }, headlineSub(result)));
  banner.appendChild(bannerText);
  card.appendChild(banner);

  const answers = answerEntries(state.answers);
  if (answers.length) {
    card.appendChild(h("div", { className: "ococ-section-title" }, "Your answers"));
    let lastSection = "";
    for (const entry of answers) {
      if (entry.section && entry.section !== lastSection) {
        card.appendChild(h("div", { className: "ococ-eyebrow" }, entry.section));
        lastSection = entry.section;
      }
      const row = h("div", { className: "ococ-answer-row" });
      row.appendChild(h("span", { className: "ococ-answer-label" }, entry.label));
      row.appendChild(h("span", { className: "ococ-answer-value" }, entry.value));
      card.appendChild(row);
    }
  }

  if (result.status_changes.length) {
    card.appendChild(h("div", { className: "ococ-section-title" }, "Status changes"));
    for (const sc of result.status_changes) {
      const title = h("strong", {}, sc.title);
      const body = document.createElement("p");
      body.textContent = sc.body;
      body.style.marginTop = "0.2rem";
      card.appendChild(title);
      card.appendChild(body);
    }
  }

  if (result.obligations.length) {
    card.appendChild(h("div", { className: "ococ-section-title" }, "Your obligations"));
    const table = h("table", { className: "ococ-table" });
    const thead = document.createElement("thead");
    thead.appendChild(h("tr", {},
      h("th", {}, "Obligation"),
      h("th", {}, "Reference"),
      h("th", {}, "Summary"),
    ));
    table.appendChild(thead);
    const tbody = document.createElement("tbody");
    for (const ob of result.obligations) {
      const summary = ob.body.length > 140 ? ob.body.slice(0, 140) + "…" : ob.body;
      tbody.appendChild(h("tr", {},
        h("td", {}, h("strong", {}, ob.title)),
        h("td", {}, ob.article_ref),
        h("td", {}, summary),
      ));
    }
    table.appendChild(tbody);
    card.appendChild(table);
  }

  const pathDiv = h("div", { className: "ococ-path" });
  const pathDetails = document.createElement("details");
  pathDetails.appendChild(h("summary", {}, "Determination path"));
  const pathBody = document.createElement("div");
  pathBody.style.paddingTop = "0.4rem";
  for (const step of result.determination_path) {
    pathBody.appendChild(h("code", {}, step));
  }
  pathDetails.appendChild(pathBody);
  pathDiv.appendChild(pathDetails);
  card.appendChild(pathDiv);

  card.appendChild(h("div", { className: "ococ-section-title" }, "Export"));
  const exportRow = h("div", { className: "ococ-export" });

  const btnJson = h("button", { className: "ococ-btn ococ-btn-secondary", type: "button" }, "Download JSON");
  (btnJson as HTMLButtonElement).onclick = () =>
    downloadFile("eu-ai-act-result.json", renderJson(result), "application/json");

  const btnMd = h("button", { className: "ococ-btn ococ-btn-secondary", type: "button" }, "Download Markdown");
  (btnMd as HTMLButtonElement).onclick = () =>
    downloadFile("eu-ai-act-result.md", renderMarkdown(result), "text/markdown");

  const btnPrint = h("button", { className: "ococ-btn ococ-btn-secondary", type: "button" }, "Print / Save PDF");
  (btnPrint as HTMLButtonElement).onclick = () => window.print();

  exportRow.appendChild(btnJson);
  exportRow.appendChild(btnMd);
  exportRow.appendChild(btnPrint);
  card.appendChild(exportRow);

  if (!isLocalCliServed()) {
    card.appendChild(h("div", { className: "ococ-section-title" }, "Email a copy"));
    const emailRow = h("div", { className: "ococ-email" });
    const emailInput = h("input", {
      type: "email",
      placeholder: "you@example.com",
      "aria-label": "Email address to send a copy of your result",
    });
    const emailBtn = h("button", { className: "ococ-btn ococ-btn-secondary", type: "button" }, "Send");
    const emailStatus = h("p", { className: "ococ-email-status" });

    (emailBtn as HTMLButtonElement).onclick = () => {
      const toEmail = (emailInput as HTMLInputElement).value.trim();
      if (!toEmail.includes("@") || !toEmail.includes(".")) {
        emailStatus.textContent = "Enter a valid email address.";
        emailStatus.className = "ococ-email-status ococ-email-error";
        return;
      }
      const originalLabel = emailBtn.textContent ?? "Send";
      (emailBtn as HTMLButtonElement).disabled = true;
      (emailInput as HTMLInputElement).disabled = true;
      emailBtn.textContent = "Sending…";
      emailStatus.textContent = "";
      emailStatus.className = "ococ-email-status";
      emailResult(state.answers, toEmail)
        .then(() => {
          emailStatus.textContent = "Sent — check your inbox.";
          emailStatus.className = "ococ-email-status ococ-email-success";
        })
        .catch((err: unknown) => {
          const reason = err instanceof Error ? err.message : "Could not send the email.";
          emailStatus.textContent = `${reason} Try one of the downloads above instead.`;
          emailStatus.className = "ococ-email-status ococ-email-error";
        })
        .finally(() => {
          (emailBtn as HTMLButtonElement).disabled = false;
          (emailInput as HTMLInputElement).disabled = false;
          emailBtn.textContent = originalLabel;
        });
    };

    emailRow.appendChild(emailInput);
    emailRow.appendChild(emailBtn);
    card.appendChild(emailRow);
    card.appendChild(emailStatus);
  }

  const actions = h("div", { className: "ococ-actions" });
  const restart = h("button", { className: "ococ-btn ococ-btn-secondary", type: "button" }, "← Start over");
  (restart as HTMLButtonElement).onclick = () => {
    state.step = 0;
    state.answers = {};
    state.result = null;
    renderQuestion(state, root);
  };
  actions.appendChild(restart);
  card.appendChild(actions);

  card.appendChild(h("p", { className: "ococ-disclaimer" }, DISCLAIMER));
  frame.appendChild(card);
  root.appendChild(frame);
}

// ── public mount ──────────────────────────────────────────────────────────────

export function mount(selector = "#ococ-checker") {
  const root = document.querySelector<HTMLElement>(selector);
  if (!root) return;
  if (root.dataset.ococMounted === "true") return;
  root.dataset.ococMounted = "true";
  injectStyles();
  const state: State = { step: 0, answers: {}, result: null };
  renderQuestion(state, root);
}

export { CHECKER_VERSION };
