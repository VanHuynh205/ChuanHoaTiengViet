import { expect, test, type Page } from "@playwright/test";

async function login(page: Page, identifier: string, password: string) {
  await page.goto("/login");
  await page.getByTestId("login-identifier").fill(identifier);
  await page.getByTestId("login-password").fill(password);
  await page.getByTestId("login-submit").click();
}

test("admin can open the moderation page from the left sidebar on desktop", async ({ page }) => {
  await login(page, "admin_main", "Admin@123");

  await expect(page.getByTestId("nav-admin-moderation")).toBeVisible();
  await page.getByTestId("nav-admin-moderation").click();

  await expect(page).toHaveURL(/\/admin\/moderation$/);
  await expect(page.getByTestId("pending-table")).toBeVisible();
});

test("workspace stays usable on mobile without page-level horizontal overflow", async ({ page }) => {
  await login(page, "demo_user_01", "User@123");

  await expect(page.getByTestId("live-input-editor")).toBeVisible();
  await expect(page.getByTestId("normalize-status")).toContainText("Chờ văn bản", { timeout: 15_000 });
  await expect(page.getByTestId("normalized-output-panel")).toBeVisible();

  const hasPageOverflow = await page.evaluate(
    () => document.documentElement.scrollWidth > window.innerWidth + 1,
  );
  expect(hasPageOverflow).toBeFalsy();
});
