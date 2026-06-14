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
  "This tool automates the Future of Life Institute compliance checker logic " +
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

// ── CSS (injected once, uses Material CSS vars) ───────────────────────────────

const CSS = `
#ococ-checker {
  font-family: var(--md-text-font, system-ui, sans-serif);
  max-width: 720px;
  margin: 0 auto;
}
.ococ-card {
  border: 1px solid var(--md-default-fg-color--lightest, #e0e0e0);
  border-radius: 12px;
  padding: 1.5rem 1.75rem;
  margin-bottom: 1rem;
  background: var(--md-default-bg-color, #fff);
  box-shadow: 0 1px 2px rgba(0,0,0,0.04), 0 8px 24px rgba(0,0,0,0.05);
}
.ococ-eyebrow {
  font-size: 0.72rem;
  font-weight: 700;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: var(--md-primary-fg-color, #2563eb);
  margin-bottom: 0.5rem;
}
.ococ-progress {
  font-size: 0.78rem;
  color: var(--md-default-fg-color--light, #666);
  margin-bottom: 0.4rem;
}
.ococ-progress-bar {
  height: 6px;
  border-radius: 3px;
  background: var(--md-default-fg-color--lightest, #e0e0e0);
  margin-bottom: 1.25rem;
  overflow: hidden;
}
.ococ-progress-fill {
  height: 100%;
  border-radius: 3px;
  background: var(--md-primary-fg-color, #2563eb);
  transition: width 0.3s ease;
}
.ococ-question {
  font-size: 1.2rem;
  font-weight: 700;
  line-height: 1.35;
  margin-bottom: 0.85rem;
  color: var(--md-default-fg-color, #222);
}
.ococ-help details {
  margin-bottom: 1rem;
  font-size: 0.88rem;
  color: var(--md-default-fg-color--light, #555);
}
.ococ-help summary {
  cursor: pointer;
  color: var(--md-primary-fg-color, #2563eb);
  font-weight: 500;
  list-style: none;
}
.ococ-help summary::before { content: "ⓘ "; }
.ococ-help summary::-webkit-details-marker { display: none; }
.ococ-help p { margin: 0.5rem 0 0; line-height: 1.5; }

/* option list (select + multi) */
.ococ-options { display: flex; flex-direction: column; gap: 0.6rem; }
.ococ-option {
  display: flex;
  align-items: flex-start;
  gap: 0.75rem;
  width: 100%;
  text-align: left;
  padding: 0.85rem 1rem;
  border: 1.5px solid var(--md-default-fg-color--lightest, #e0e0e0);
  border-radius: 10px;
  background: var(--md-default-bg-color, #fff);
  color: var(--md-default-fg-color, #222);
  cursor: pointer;
  font: inherit;
  transition: border-color 0.15s, background 0.15s, transform 0.05s;
}
.ococ-option:hover { border-color: var(--md-primary-fg-color, #2563eb); }
.ococ-option:active { transform: translateY(1px); }
.ococ-option[aria-checked="true"] {
  border-color: var(--md-primary-fg-color, #2563eb);
  background: var(--ococ-accent-soft, var(--md-default-fg-color--lightest, #eef2ff));
  box-shadow: inset 0 0 0 1px var(--md-primary-fg-color, #2563eb);
}
.ococ-option-marker {
  flex: 0 0 auto;
  width: 20px;
  height: 20px;
  margin-top: 1px;
  border-radius: 50%;
  border: 2px solid var(--md-default-fg-color--light, #aaa);
  display: grid;
  place-items: center;
}
.ococ-option--multi .ococ-option-marker { border-radius: 5px; }
.ococ-option[aria-checked="true"] .ococ-option-marker {
  border-color: var(--md-primary-fg-color, #2563eb);
  background: var(--md-primary-fg-color, #2563eb);
}
.ococ-option-marker svg { width: 12px; height: 12px; display: none; }
.ococ-option[aria-checked="true"] .ococ-option-marker svg { display: block; }
.ococ-option-body { display: flex; flex-direction: column; gap: 0.15rem; }
.ococ-option-title { font-weight: 600; font-size: 0.98rem; }
.ococ-option-desc {
  font-size: 0.84rem;
  line-height: 1.45;
  color: var(--md-default-fg-color--light, #666);
}

/* yes / no */
.ococ-yesno { display: flex; gap: 0.75rem; }
.ococ-yesno .ococ-option { flex: 1 1 0; justify-content: center; align-items: center; font-weight: 600; font-size: 1.05rem; padding: 1rem; }
.ococ-yesno .ococ-option-body { align-items: center; }

/* navigation */
.ococ-actions {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  margin-top: 1.5rem;
  flex-wrap: wrap;
}
.ococ-spacer { flex: 1 1 auto; }
.ococ-btn {
  padding: 0.55rem 1.2rem;
  border-radius: 8px;
  border: 1.5px solid transparent;
  cursor: pointer;
  font-size: 0.9rem;
  font-weight: 600;
  transition: opacity 0.15s, background 0.15s;
}
.ococ-btn:hover { opacity: 0.88; }
.ococ-btn-primary { background: var(--md-primary-fg-color, #2563eb); color: #fff; }
.ococ-btn-secondary {
  background: transparent;
  border-color: var(--md-default-fg-color--lightest, #d0d0d0);
  color: var(--md-default-fg-color--light, #555);
}
.ococ-btn:disabled { opacity: 0.4; cursor: default; }

/* focus visibility (keyboard) */
.ococ-option:focus-visible,
.ococ-btn:focus-visible,
.ococ-help summary:focus-visible {
  outline: 2px solid var(--md-primary-fg-color, #2563eb);
  outline-offset: 2px;
}

/* result */
.ococ-result-headline {
  font-size: 1.2rem;
  font-weight: 700;
  padding: 0.7rem 1.1rem;
  border-radius: 8px;
  margin-bottom: 1.25rem;
  display: inline-block;
}
.ococ-result-prohibited { background: #fee2e2; color: #b91c1c; }
.ococ-result-high { background: #fef3c7; color: #92400e; }
.ococ-result-in-scope { background: #d1fae5; color: #065f46; }
.ococ-result-out { background: var(--md-default-fg-color--lightest, #f3f4f6); color: var(--md-default-fg-color--light, #555); }
.ococ-section-title {
  font-size: 0.92rem;
  font-weight: 700;
  margin: 1.25rem 0 0.5rem;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  color: var(--md-default-fg-color--light, #555);
}
.ococ-table { width: 100%; border-collapse: collapse; font-size: 0.88rem; margin-bottom: 0.5rem; }
.ococ-table th {
  text-align: left; padding: 0.45rem 0.65rem;
  background: var(--md-default-fg-color--lightest, #f3f4f6);
  font-weight: 600; color: var(--md-default-fg-color, #333);
}
.ococ-table td {
  padding: 0.45rem 0.65rem;
  border-top: 1px solid var(--md-default-fg-color--lightest, #e5e7eb);
  vertical-align: top; color: var(--md-default-fg-color, #333);
}
.ococ-path details { font-size: 0.82rem; margin-top: 0.75rem; }
.ococ-path summary { cursor: pointer; color: var(--md-default-fg-color--light, #666); }
.ococ-path code {
  display: inline-block; background: var(--md-code-bg-color, #f5f5f5);
  border-radius: 4px; padding: 0.08rem 0.4rem; font-size: 0.8rem; margin: 0.1rem;
  color: var(--md-default-fg-color, #333);
}
.ococ-export { display: flex; gap: 0.5rem; flex-wrap: wrap; margin-top: 0.75rem; }
.ococ-disclaimer {
  font-size: 0.78rem; color: var(--md-default-fg-color--light, #666);
  margin-top: 1.5rem; padding-top: 1rem;
  border-top: 1px solid var(--md-default-fg-color--lightest, #e5e7eb);
  line-height: 1.5;
}
.ococ-privacy { font-size: 0.82rem; color: var(--md-default-fg-color--light, #666); margin: 0 0 1rem; }

@media (max-width: 520px) {
  .ococ-card { padding: 1.15rem 1.1rem; }
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
  for (const [k, v] of Object.entries(attrs)) {
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
  const pct = Math.round((state.step / total) * 100);

  root.innerHTML = "";
  const card = h("div", { className: "ococ-card" });

  if (state.step === 0) {
    card.appendChild(h("p", { className: "ococ-privacy" }, PRIVACY_NOTE));
  }

  if (q.section) {
    card.appendChild(h("div", { className: "ococ-eyebrow" }, q.section));
  }

  card.appendChild(
    h("div", { className: "ococ-progress" }, `Step ${state.step + 1} of ${total}`)
  );
  const bar = h("div", { className: "ococ-progress-bar" });
  const fill = h("div", { className: "ococ-progress-fill" });
  fill.style.width = `${pct}%`;
  bar.appendChild(fill);
  card.appendChild(bar);

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
  root.appendChild(card);

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
  const role = result.effective_entity
    ? ` — ${result.effective_entity.replace(/_/g, " ")}`
    : "";
  if (result.is_prohibited) return `Prohibited practice${role}`;
  if (result.is_high_risk) return `High risk${role}`;
  if (result.in_scope) return `In scope${role}`;
  return `Out of scope${role}`;
}

function downloadFile(filename: string, content: string, mime: string) {
  const blob = new Blob([content], { type: mime });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
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

  const card = h("div", { className: "ococ-card" });

  const hl = h("div", { className: `ococ-result-headline ${headlineClass(result)}` },
    headlineText(result));
  card.appendChild(hl);

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

  const restartRow = h("div", { style: "margin-top:1.25rem" });
  const restart = h("button", { className: "ococ-btn ococ-btn-secondary", type: "button" }, "← Start over");
  (restart as HTMLButtonElement).onclick = () => {
    state.step = 0;
    state.answers = {};
    state.result = null;
    renderQuestion(state, root);
  };
  restartRow.appendChild(restart);
  card.appendChild(restartRow);

  card.appendChild(h("p", { className: "ococ-disclaimer" }, DISCLAIMER));
  root.appendChild(card);
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
