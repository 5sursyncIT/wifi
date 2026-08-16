#!/usr/bin/env node
/**
 * Enforces the captive portal's initial JavaScript budget (cahier des charges §12.1).
 *
 * Reads the prerendered HTML of the root route and measures every byte of JavaScript
 * the browser loads with it — external files *and* inline module scripts, which some
 * bundlers emit instead of separate files. Working from the emitted HTML rather than a
 * bundler manifest keeps the check honest across bundlers; the Astro and Next.js build
 * layouts are both recognised.
 *
 * Usage: node scripts/check-bundle-budget.mjs <app-dir> [budget-kb]
 */
import { gzipSync } from "node:zlib";
import { existsSync, readFileSync, statSync } from "node:fs";
import { join } from "node:path";

const appDir = process.argv[2];
const budgetKb = Number(process.argv[3] ?? 150);

if (!appDir) {
  console.error("Usage: node scripts/check-bundle-budget.mjs <app-dir> [budget-kb]");
  process.exit(2);
}

// Each layout: where the root route's HTML lives, and how an asset URL maps to a file.
const LAYOUTS = [
  {
    name: "astro",
    html: join(appDir, "dist", "index.html"),
    toFile: (url) => join(appDir, "dist", url.replace(/^\//, "")),
  },
  {
    name: "next",
    html: join(appDir, ".next", "server", "app", "index.html"),
    toFile: (url) => join(appDir, ".next", url.replace("/_next/", "")),
  },
];

const layout = LAYOUTS.find((candidate) => existsSync(candidate.html));

if (!layout) {
  console.error(
    `Build introuvable. Cherché :\n  ${LAYOUTS.map((l) => l.html).join("\n  ")}\n` +
      "Lancez d'abord `pnpm build`.",
  );
  process.exit(2);
}

const html = readFileSync(layout.html, "utf8");

// External scripts and module preloads alike: both are fetched on first load.
const externalUrls = [...new Set([...html.matchAll(/["'](\/[^"']+?\.js)["']/g)].map((m) => m[1]))];

// Inline scripts ship inside the HTML response and count just as much.
const inlineBodies = [];
for (const [, attrs, body] of html.matchAll(/<script\b([^>]*)>([\s\S]*?)<\/script>/g)) {
  if (/\bsrc\s*=/.test(attrs)) continue;
  const type = attrs.match(/\btype\s*=\s*["']([^"']+)["']/)?.[1];
  if (type && !["module", "text/javascript", "application/javascript"].includes(type)) continue;
  if (body.trim()) inlineBodies.push(body);
}

let total = 0;
const missing = [];

for (const url of externalUrls) {
  const file = layout.toFile(url);
  if (!existsSync(file)) {
    missing.push(url);
    continue;
  }
  total += gzipSync(readFileSync(file)).length;
}

if (missing.length > 0) {
  console.error(`Scripts référencés mais absents du build :\n  ${missing.join("\n  ")}`);
  process.exit(2);
}

// Inline scripts travel in a single HTML response, so they compress together.
const inlineGzip = inlineBodies.length > 0 ? gzipSync(inlineBodies.join("\n")).length : 0;
total += inlineGzip;

const budgetBytes = budgetKb * 1024;
const htmlGzip = gzipSync(html).length;
const cssGzip = [...new Set([...html.matchAll(/["'](\/[^"']+?\.css)["']/g)].map((m) => m[1]))]
  .map((url) => layout.toFile(url))
  .filter((file) => existsSync(file) && statSync(file).isFile())
  .reduce((sum, file) => sum + gzipSync(readFileSync(file)).length, 0);

console.log(`Build          : ${layout.name}`);
console.log(
  `JavaScript     : ${(total / 1024).toFixed(1)} Ko gzip ` +
    `(${externalUrls.length} externe(s), ${inlineBodies.length} en ligne)`,
);
console.log(`Budget JS      : ${budgetKb} Ko gzip`);
console.log(
  `Page complète  : ${((htmlGzip + cssGzip) / 1024).toFixed(1)} Ko gzip ` +
    `(HTML + CSS, JS en ligne inclus) — indicatif`,
);

if (total > budgetBytes) {
  console.error(`\n✗ Budget dépassé de ${((total - budgetBytes) / 1024).toFixed(1)} Ko.`);
  process.exit(1);
}

console.log(`\n✓ Sous le budget (${((budgetBytes - total) / 1024).toFixed(1)} Ko de marge).`);
