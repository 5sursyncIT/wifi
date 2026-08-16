import { defineConfig, devices } from "@playwright/test";

// Same port as the real portal so the configured CORS origin applies unchanged.
const PORT = 3000;

export default defineConfig({
  testDir: "./e2e",
  fullyParallel: false,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 1 : 0,
  workers: 1,
  reporter: process.env.CI ? "line" : "list",
  use: {
    baseURL: `http://localhost:${PORT}`,
    trace: "on-first-retry",
  },
  projects: [
    {
      name: "android-entree-de-gamme",
      // The portal is designed for this device class first (§12.1), so the journey
      // is verified on it rather than on a desktop viewport.
      use: { ...devices["Galaxy S5"] },
    },
  ],
  webServer: {
    command: `pnpm exec astro preview --port ${PORT}`,
    url: `http://localhost:${PORT}`,
    reuseExistingServer: !process.env.CI,
    timeout: 60_000,
  },
});
