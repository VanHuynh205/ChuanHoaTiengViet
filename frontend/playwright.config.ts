import { defineConfig, devices } from "@playwright/test";

export default defineConfig({
  testDir: "./tests/e2e",
  fullyParallel: false,
  forbidOnly: !!process.env.CI,
  workers: 1,
  retries: process.env.CI ? 1 : 0,
  reporter: [["list"], ["html", { open: "never" }]],
  use: {
    baseURL: "http://localhost:5173",
    trace: "on-first-retry",
    screenshot: "only-on-failure",
    video: "off",
  },
  projects: [
    {
      name: "desktop-edge",
      use: {
        browserName: "chromium",
        channel: "msedge",
        viewport: { width: 1440, height: 960 },
      },
    },
    {
      name: "tablet-edge",
      use: {
        browserName: "chromium",
        channel: "msedge",
        ...devices["iPad (gen 7)"],
      },
    },
    {
      name: "mobile-edge",
      use: {
        browserName: "chromium",
        channel: "msedge",
        ...devices["Pixel 7"],
      },
    },
  ],
  webServer: [
    {
      command: "..\\scripts\\run_backend_e2e.cmd",
      url: "http://localhost:8000/api/health",
      reuseExistingServer: true,
      timeout: 120_000,
    },
    {
      command: "node node_modules/vite/bin/vite.js --host localhost --port 5173",
      url: "http://localhost:5173",
      reuseExistingServer: true,
      timeout: 120_000,
    },
  ],
});
