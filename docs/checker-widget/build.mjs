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

  // ── 3. Build self-contained local HTML for `opencomplai checker --local` ──
  const { execFileSync } = await import("node:child_process");
  execFileSync(process.execPath, [
    path.join(__dirname, "build-local-html.mjs"),
  ], { stdio: "inherit" });
}
