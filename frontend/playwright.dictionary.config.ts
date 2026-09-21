import { defineConfig } from "@playwright/test";

export default defineConfig({
  testDir: "./tests/dictionary",
  workers: 1,
  timeout: 45000,
  reporter: "list",
  use: { baseURL: "http://127.0.0.1:5188", browserName: "chromium", channel: "msedge" },
  webServer: [
    { command: "..\\.venv\\Scripts\\python.exe ..\\backend\\tests\\serve_dictionary_fixture.py",
      url: "http://127.0.0.1:8018/__test/session", reuseExistingServer: false,
      env: { WEB_ORIGIN: "http://127.0.0.1:5188", AI_DISABLE_NETWORK: "1" } },
    { command: "node node_modules/vite/bin/vite.js --host 127.0.0.1 --port 5188 --strictPort",
      url: "http://127.0.0.1:5188", reuseExistingServer: false,
      env: { VITE_API_BASE_URL: "http://127.0.0.1:8018" } },
  ],
});
