/**
 * Build script: copies the three JSON catalogs from packages/core, then bundles
 * src/index.ts into ../../src/assets/js/checker-widget.js (inlined catalogs,
 * no runtime network calls).
 */
import * as esbuild from "esbuild";
import * as fs from "node:fs";
import * as path from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const root = path.resolve(__dirname, "../..");

// ── 1. Copy catalogs from packages/core into src/data/ so they're importable ──
const DATA_SRC = path.join(
  root,
  "packages/core/src/opencomplai_core/compliance_checker/data"
);
const DATA_DST = path.join(__dirname, "src/data");
fs.mkdirSync(DATA_DST, { recursive: true });

for (const file of ["obligations.json", "status_changes.json", "help_content.json"]) {
  fs.copyFileSync(path.join(DATA_SRC, file), path.join(DATA_DST, file));
}
console.log("✓ catalogs copied");

// ── 2. Bundle ──
const outDir = path.join(__dirname, "../../docs/src/assets/js");
fs.mkdirSync(outDir, { recursive: true });

const watch = process.argv.includes("--watch");

const ctx = await esbuild.context({
  entryPoints: [path.join(__dirname, "src/index.ts")],
  bundle: true,
  minify: !watch,
  format: "iife",
  globalName: "OcocChecker",
  outfile: path.join(outDir, "checker-widget.js"),
  target: ["es2020", "chrome90", "firefox90", "safari14"],
  logLevel: "info",
});

if (watch) {
  await ctx.watch();
  console.log("watching…");
} else {
  await ctx.rebuild();
  await ctx.dispose();
  console.log("✓ bundle written to docs/src/assets/js/checker-widget.js");

  // ── 3. Cache-bust the widget script in mkdocs.yml with the engine version ──
  // checker-widget.js keeps a stable filename (edge/browser cache it for up to
  // a day), so without a query param, redeploys can serve a stale bundle until
  // caches expire. Tie the busting param to CHECKER_VERSION so it only changes
  // when the engine actually changes.
  const engineSrc = fs.readFileSync(path.join(__dirname, "src/engine.ts"), "utf8");
  const versionMatch = engineSrc.match(/CHECKER_VERSION\s*=\s*"([^"]+)"/);
  if (!versionMatch) {
    throw new Error("Could not find CHECKER_VERSION in src/engine.ts");
  }
  const version = versionMatch[1];
  const mkdocsPath = path.join(root, "docs/mkdocs.yml");
  const mkdocsSrc = fs.readFileSync(mkdocsPath, "utf8");
  const busted = mkdocsSrc.replace(
    /assets\/js\/checker-widget\.js(\?v=[^\s]*)?/,
    `assets/js/checker-widget.js?v=${version}`
  );
  fs.writeFileSync(mkdocsPath, busted);
  console.log(`✓ mkdocs.yml cache-busted with ?v=${version}`);

  // ── 4. Build self-contained local HTML for `opencomplai checker --local` ──
  const { execFileSync } = await import("node:child_process");
  execFileSync(process.execPath, [
    path.join(__dirname, "build-local-html.mjs"),
  ], { stdio: "inherit" });
}
