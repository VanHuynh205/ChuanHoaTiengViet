import { defineConfig, loadEnv } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig(({ command, mode }) => {
  const env = loadEnv(mode, process.cwd(), "");

  // Fail the BUILD rather than shipping a bundle that points at a dev host.
  // `src/lib/api.ts` falls back to the same origin in production, so this only
  // has to be set when the API lives somewhere else.
  if (command === "build" && env.VITE_API_BASE_URL === undefined && mode === "production") {
    // eslint-disable-next-line no-console
    console.warn(
      "[vite] VITE_API_BASE_URL is not set — the bundle will call the API on the same origin.",
    );
  }
  if (command === "build" && env.VITE_API_BASE_URL?.includes("localhost")) {
    throw new Error(
      "[vite] VITE_API_BASE_URL points at localhost; refusing to build a production bundle.",
    );
  }

  return {
    plugins: [react()],
    test: {
      environment: "jsdom",
      globals: true,
      setupFiles: "./src/test/setup.ts",
      include: ["src/**/*.test.ts", "src/**/*.test.tsx"],
      exclude: ["tests/e2e/**", "node_modules/**"],
    },
  };
});
