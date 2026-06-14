/**
 * Produces packages/cli/src/opencomplai_cli/data/checker-local.html —
 * a fully self-contained single-file checker used by `opencomplai checker --local`.
 * The widget JS, brand logos and favicon are all inlined so it works with zero
 * network access. Light/dark is driven by CSS custom properties; an in-page
 * toggle overrides the OS preference and persists the choice in localStorage.
 */
import * as fs from "node:fs";
import * as path from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const root = path.resolve(__dirname, "../..");

const bundlePath = path.join(root, "docs/src/assets/js/checker-widget.js");
const outPath = path.join(
  root,
  "packages/cli/src/opencomplai_cli/data/checker-local.html"
);

if (!fs.existsSync(bundlePath)) {
  console.error("Bundle not found — run `node build.mjs` first.");
  process.exit(1);
}

const js = fs.readFileSync(bundlePath, "utf-8");

// ── inline brand assets as data URIs (self-contained, offline) ────────────────
function svgDataUri(relPath) {
  const abs = path.join(root, relPath);
  const b64 = fs.readFileSync(abs).toString("base64");
  return `data:image/svg+xml;base64,${b64}`;
}

const logoLight = svgDataUri("docs/src/logo/light.svg");
const logoDark = svgDataUri("docs/src/logo/dark.svg");
const favicon = svgDataUri("docs/favicon.svg");

// Dark-theme variable block, reused for explicit data-theme="dark" and for the
// OS preference when the user has not made an explicit choice.
const DARK_VARS = `
  --md-primary-fg-color: #60a5fa;
  --md-default-fg-color: #f3f4f6;
  --md-default-fg-color--light: #9ca3af;
  --md-default-fg-color--lightest: #374151;
  --md-default-bg-color: #0e1117;
  --md-code-bg-color: #1f2937;
  --ococ-page-bg: #0a0d12;
  --ococ-bar-bg: #11151c;
  --ococ-border: #1f2937;
  --ococ-accent-soft: rgba(96,165,250,0.16);
`;

const html = `<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>EU AI Act Compliance Checker — Opencomplai</title>
  <link rel="icon" type="image/svg+xml" href="${favicon}">
  <script>
    /* Apply a saved theme before first paint to avoid a flash. */
    (function () {
      try {
        var t = localStorage.getItem("ococ-theme");
        if (t === "dark" || t === "light") {
          document.documentElement.setAttribute("data-theme", t);
        }
      } catch (e) { /* ignore */ }
    })();
  </script>
  <style>
    *, *::before, *::after { box-sizing: border-box; }
    :root {
      --md-primary-fg-color: #2563eb;
      --md-default-fg-color: #1f2937;
      --md-default-fg-color--light: #6b7280;
      --md-default-fg-color--lightest: #e5e7eb;
      --md-default-bg-color: #ffffff;
      --md-code-bg-color: #f3f4f6;
      --md-text-font: system-ui, -apple-system, "Segoe UI", Roboto, sans-serif;
      --ococ-page-bg: #f6f7f9;
      --ococ-bar-bg: #ffffff;
      --ococ-border: #e5e7eb;
      --ococ-accent-soft: rgba(37,99,235,0.10);
    }
    :root[data-theme="dark"] {${DARK_VARS}}
    @media (prefers-color-scheme: dark) {
      :root:not([data-theme="light"]) {${DARK_VARS}}
    }
    html, body { margin: 0; padding: 0; }
    body {
      font-family: var(--md-text-font);
      background: var(--ococ-page-bg);
      color: var(--md-default-fg-color);
      min-height: 100vh;
    }
    a { color: var(--md-primary-fg-color); }

    .ococ-topbar {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 1rem;
      padding: 0.85rem 1.25rem;
      background: var(--ococ-bar-bg);
      border-bottom: 1px solid var(--ococ-border);
      position: sticky;
      top: 0;
      z-index: 10;
    }
    .ococ-brand { display: flex; align-items: center; }
    .ococ-brand img { height: 26px; width: auto; display: block; }
    .ococ-logo--dark { display: none; }
    :root[data-theme="dark"] .ococ-logo--light { display: none; }
    :root[data-theme="dark"] .ococ-logo--dark { display: block; }
    @media (prefers-color-scheme: dark) {
      :root:not([data-theme="light"]) .ococ-logo--light { display: none; }
      :root:not([data-theme="light"]) .ococ-logo--dark { display: block; }
    }

    .ococ-theme-toggle {
      display: inline-flex;
      align-items: center;
      gap: 0.4rem;
      padding: 0.4rem 0.8rem;
      border: 1px solid var(--ococ-border);
      border-radius: 999px;
      background: transparent;
      color: var(--md-default-fg-color--light);
      font: inherit;
      font-size: 0.85rem;
      cursor: pointer;
    }
    .ococ-theme-toggle:hover { color: var(--md-default-fg-color); }
    .ococ-theme-toggle:focus-visible {
      outline: 2px solid var(--md-primary-fg-color);
      outline-offset: 2px;
    }

    main { padding: 2rem 1rem 1rem; }
    .ococ-intro { max-width: 720px; margin: 0 auto 1.5rem; }
    .ococ-intro h1 { font-size: 1.6rem; margin: 0 0 0.35rem; }
    .ococ-intro p { color: var(--md-default-fg-color--light); font-size: 0.92rem; margin: 0; line-height: 1.5; }

    footer {
      max-width: 720px;
      margin: 2rem auto 3rem;
      padding-top: 1rem;
      border-top: 1px solid var(--ococ-border);
      color: var(--md-default-fg-color--light);
      font-size: 0.78rem;
      line-height: 1.5;
      text-align: center;
    }
  </style>
</head>
<body>
  <header class="ococ-topbar">
    <span class="ococ-brand">
      <img class="ococ-logo--light" src="${logoLight}" alt="Opencomplai">
      <img class="ococ-logo--dark" src="${logoDark}" alt="Opencomplai">
    </span>
    <button id="ococ-theme-toggle" class="ococ-theme-toggle" type="button" aria-pressed="false">☾ Dark</button>
  </header>

  <main>
    <div class="ococ-intro">
      <h1>EU AI Act applicability checker</h1>
      <p>
        Answer a short questionnaire to find out whether the EU AI Act applies to
        your AI system, in what operator role, at what risk tier, and which
        obligations follow. Engine version <strong>fli-2025-07-28</strong>.
      </p>
    </div>
    <div id="ococ-checker"></div>
  </main>

  <footer>
    Opencomplai · checker fli-2025-07-28 ·
    <a href="https://opencomplai.com" target="_blank" rel="noopener">opencomplai.com</a><br>
    Not legal advice — informational only. Seek qualified legal counsel.
  </footer>

  <script>${js}</script>
  <script>
    /* Theme toggle: flip the explicit choice, persist it, update the label. */
    (function () {
      var rootEl = document.documentElement;
      var btn = document.getElementById("ococ-theme-toggle");
      function isDark() {
        var explicit = rootEl.getAttribute("data-theme");
        if (explicit) return explicit === "dark";
        return window.matchMedia && window.matchMedia("(prefers-color-scheme: dark)").matches;
      }
      function refresh() {
        var dark = isDark();
        btn.setAttribute("aria-pressed", String(dark));
        btn.textContent = dark ? "☀ Light" : "☾ Dark";
      }
      btn.addEventListener("click", function () {
        var next = isDark() ? "light" : "dark";
        rootEl.setAttribute("data-theme", next);
        try { localStorage.setItem("ococ-theme", next); } catch (e) { /* ignore */ }
        refresh();
      });
      if (window.matchMedia) {
        window.matchMedia("(prefers-color-scheme: dark)").addEventListener("change", refresh);
      }
      refresh();
    })();
  </script>
</body>
</html>`;

fs.mkdirSync(path.dirname(outPath), { recursive: true });
fs.writeFileSync(outPath, html, "utf-8");
console.log(`✓ checker-local.html written (${Math.round(html.length / 1024)} KB)`);
