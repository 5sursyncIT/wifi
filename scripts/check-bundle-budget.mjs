#!/usr/bin/env node
/**
 * Enforces the captive portal's initial JavaScript budget (cahier des charges §12.1).
 *
 * Reads the prerendered HTML of the root route and sums the gzipped size of every
 * script it references — what a phone on a slow network actually downloads. Parsing
 * the emitted HTML rather than a bundler manifest keeps this check working across
 * bundler changes.
 *
 * Usage: node scripts/check-bundle-budget.mjs <app-dir> [budget-kb]
 */
import { gzipSync } from "node:zlib";
import { existsSync, readFileSync } from "node:fs";
import { join } from "node:path";

const appDir = process.argv[2];
const budgetKb = Number(process.argv[3] ?? 150);

if (!appDir) {
  console.error("Usage: node scripts/check-bundle-budget.mjs <app-dir> [budget-kb]");
  process.exit(2);
}

const nextDir = join(appDir, ".next");
const htmlPath = join(nextDir, "server", "app", "index.html");

if (!existsSync(htmlPath)) {
  console.error(`Build introuvable : ${htmlPath}\nLancez d'abord \`pnpm build\`.`);
  process.exit(2);
}

const html = readFileSync(htmlPath, "utf8");
const references = [...new Set(html.match(/\/_next\/static\/[^"']*?\.js/g) ?? [])];

if (references.length === 0) {
  console.error("Aucun script référencé dans le HTML prérendu : vérifiez le build.");
  process.exit(2);
}

let total = 0;
const missing = [];
for (const reference of references) {
  const file = join(nextDir, reference.replace("/_next/", ""));
  if (!existsSync(file)) {
    missing.push(reference);
    continue;
  }
  total += gzipSync(readFileSync(file)).length;
}

if (missing.length > 0) {
  console.error(`Chunks référencés mais absents du build :\n  ${missing.join("\n  ")}`);
  process.exit(2);
}

const budgetBytes = budgetKb * 1024;

console.log(`Route /  —  ${references.length} scripts  —  ${(total / 1024).toFixed(1)} Ko gzip`);
console.log(`Budget   —  ${budgetKb} Ko gzip`);

if (total > budgetBytes) {
  console.error(`\n✗ Budget dépassé de ${((total - budgetBytes) / 1024).toFixed(1)} Ko.`);
  process.exit(1);
}

console.log(`\n✓ Sous le budget (${((budgetBytes - total) / 1024).toFixed(1)} Ko de marge).`);
