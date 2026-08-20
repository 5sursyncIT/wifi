/**
 * End-to-end free access journey (cahier des charges §16.2, §17 critères 1 à 3).
 *
 * Runs against the real API and the real portal build. The verification code is read
 * from the mock SMS outbox, exactly as a citizen reads their phone.
 *
 * Requires `make up && make seed` beforehand: the journey needs the demonstration
 * hotspot, its free offer and its zone policy.
 */
import { expect, test } from "@playwright/test";

const API = process.env.PUBLIC_API_BASE_URL ?? "http://localhost:8000";
const NAS_ID = "demo-nas-001";

function uniquePhone(): string {
  // A fresh number per run: the free allowance has a cooldown, so replaying the
  // journey with the same citizen would legitimately be refused.
  const suffix = String(Date.now()).slice(-7);
  return `+2217${suffix}`;
}

async function readCode(request: import("@playwright/test").APIRequestContext, phone: string) {
  const response = await request.get(`${API}/api/v1/dev/sms-outbox`);
  expect(response.ok()).toBeTruthy();
  const { messages } = await response.json();
  const mine = [...messages].reverse().find((message) => message.to === phone);
  expect(mine, `no SMS sent to ${phone}`).toBeTruthy();
  return /\b(\d{6})\b/.exec(mine.body)![1];
}

test("un citoyen obtient un accès gratuit en trois écrans", async ({ page, request }) => {
  const phone = uniquePhone();

  // Écran 1 — la zone est résolue par la borne, les offres s'affichent.
  await page.goto(`/?nas_id=${NAS_ID}`);
  await expect(page.getByRole("heading", { name: "Place de l'Indépendance" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Accès gratuit" })).toBeVisible();

  await page.getByRole("button", { name: "Se connecter gratuitement" }).click();

  // Écran 2 — identification et consentement explicite.
  await page.getByLabel("Numéro de téléphone").fill(phone);
  await page.getByLabel(/J’accepte les conditions/).check();
  await page.getByRole("button", { name: "Recevoir un code" }).click();

  // Écran 3 — le code, puis l'accès.
  await expect(page.getByRole("heading", { name: "Code reçu par SMS" })).toBeVisible();
  await page.getByLabel("Code à six chiffres").fill(await readCode(request, phone));
  await page.getByRole("button", { name: "Valider" }).click();

  await expect(page.getByRole("heading", { name: "Vous êtes connecté" })).toBeVisible();
});

test("un code erroné est refusé sans ouvrir l'accès", async ({ page }) => {
  const phone = uniquePhone();

  await page.goto(`/?nas_id=${NAS_ID}`);
  await page.getByRole("button", { name: "Se connecter gratuitement" }).click();
  await page.getByLabel("Numéro de téléphone").fill(phone);
  await page.getByLabel(/J’accepte les conditions/).check();
  await page.getByRole("button", { name: "Recevoir un code" }).click();

  await page.getByLabel("Code à six chiffres").fill("000000");
  await page.getByRole("button", { name: "Valider" }).click();

  await expect(page.getByRole("alert")).toContainText("Code incorrect");
  await expect(page.getByRole("heading", { name: "Vous êtes connecté" })).toBeHidden();
});

test("une borne inconnue n'expose aucune offre", async ({ page }) => {
  await page.goto("/?nas_id=borne-qui-nexiste-pas");

  await expect(page.getByRole("heading", { name: "Connexion impossible" })).toBeVisible();
  await expect(page.getByRole("button", { name: /Se connecter/ })).toBeHidden();
});
