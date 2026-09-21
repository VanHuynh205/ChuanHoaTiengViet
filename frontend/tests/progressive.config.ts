import { defineConfig } from "@playwright/test";

export default defineConfig({
  testDir: "./progressive",
  workers: 1,
  reporter: "list",
  use: { baseURL: "http://localhost:5186", browserName: "chromium", channel: "msedge" },
  projects: [
    { name: "desktop", use: { viewport: { width: 1440, height: 960 } } },
    { name: "mobile", use: { viewport: { width: 390, height: 844 } } },
  ],
});
