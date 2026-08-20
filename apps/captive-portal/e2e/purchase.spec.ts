/**
 * End-to-end purchase journey (cahier des charges §16.2, §17 critères 4 à 6).
 *
 * Runs against the real API and the real portal build. The webhook is triggered
 * through the development helper so it is genuinely signed and genuinely verified,
 * rather than the processing function being called directly.
 *
 * Requires `make up && make seed` beforehand.
 */
import { expect, test } from "@playwright/test";

const API = process.env.PUBLIC_API_BASE_URL ?? "http://localhost:8000";
const NAS_ID = "demo-nas-001";

function uniquePhone(): string {
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

async function startPurchase(
  page: import("@playwright/test").Page,
  request: import("@playwright/test").APIRequestContext,
  phone: string,
) {
  await page.goto(`/?nas_id=${NAS_ID}`);
  await page.getByRole("button", { name: "Acheter 1 heure", exact: true }).click();
  await page.getByLabel("Numéro de téléphone").fill(phone);
  await page.getByLabel(/J’accepte les conditions/).check();
  await page.getByRole("button", { name: "Recevoir un code" }).click();
  const code = page.getByLabel("Code à six chiffres");
  await expect(code).toBeVisible();
  await code.fill(await readCode(request, phone));
  await page.getByRole("button", { name: "Valider" }).click();
  await expect(page).toHaveURL(/\/achat\?nas_id=demo-nas-001&offre=/);
}

test("un citoyen achète une offre et son accès s'active", async ({ page, request }) => {
  await startPurchase(page, request, uniquePhone());

  await expect(page.locator("#attente")).toBeVisible();
  await expect(page.locator("#instructions")).toContainText("Validez le paiement");
  await expect(page.locator("#compte-a-rebours")).toContainText("Temps restant");
  await expect(page.locator("#redirection")).toBeHidden();
  await expect(page.locator("#lien-paiement")).toBeHidden();

  const orderNumber = await page.locator("#attente").getAttribute("data-order-number");
  expect(orderNumber).toBeTruthy();
  const emitted = await request.post(`${API}/api/v1/dev/payments/emit`, {
    data: { order_number: orderNumber, status: "succeeded" },
  });
  expect(emitted.ok()).toBeTruthy();

  await expect(page.locator("#succes")).toBeVisible({ timeout: 30_000 });
  await expect(page.getByRole("heading", { name: "Votre accès est activé" })).toBeVisible();
  await expect(page.locator("#recu")).toContainText(orderNumber!);
  await expect(page.locator("#erreur")).toBeHidden();
});

test("un paiement refusé n'ouvre pas l'accès", async ({ page, request }) => {
  await startPurchase(page, request, uniquePhone());

  const orderNumber = await page.locator("#attente").getAttribute("data-order-number");
  expect(orderNumber).toBeTruthy();
  const emitted = await request.post(`${API}/api/v1/dev/payments/emit`, {
    data: { order_number: orderNumber, status: "refused" },
  });
  expect(emitted.ok()).toBeTruthy();

  await expect(page.locator("#echec")).toBeVisible();
  await expect(page.locator("#raison-echec")).toContainText("refusé");
  await expect(page.locator("#succes")).toBeHidden();
});
