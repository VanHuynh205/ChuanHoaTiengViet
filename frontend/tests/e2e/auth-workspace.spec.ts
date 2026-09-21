import { expect, test, type Page } from "@playwright/test";

const sampleText = "hôm nay đi đk thẻ ngân hàng pk";

async function login(page: Page, identifier: string, password: string) {
  await page.goto("/login");
  await page.getByTestId("login-identifier").fill(identifier);
  await page.getByTestId("login-password").fill(password);
  await page.getByTestId("login-submit").click();
}

test("user can normalize live and revise a previous ambiguity while typing", async ({ page }) => {
  await login(page, "demo_user_01", "User@123");

  const editor = page.getByTestId("live-input-editor");
  await expect(editor).toBeVisible();
  await expect(editor).toHaveValue("");

  await editor.fill(sampleText);

  await expect(page.getByTestId("normalize-status")).toContainText("Đã đồng bộ", { timeout: 15_000 });
  await expect(page.getByTestId("primary-output")).toContainText(/đăng ký|đúng không/, { timeout: 15_000 });
  await expect(page.getByTestId("ambiguity-list")).toBeVisible();

  const initialOutput = await page.getByTestId("primary-output").textContent();
  const currentMeaning = initialOutput?.includes("đăng ký") ? "đăng ký" : "đúng không";
  const targetMeaning = currentMeaning === "đăng ký" ? "đúng không" : "đăng ký";

  await page.getByRole("button", { name: currentMeaning }).click();
  await expect(page.getByRole("button", { name: "Chọn lại" })).toBeVisible({ timeout: 15_000 });

  await page.getByRole("button", { name: "Chọn lại" }).click();
  await page.getByRole("button", { name: "đk" }).click();
  await page.getByRole("button", { name: targetMeaning }).click();

  await expect(page.getByTestId("primary-output")).toContainText(targetMeaning, { timeout: 15_000 });
});

test("non-admin user is redirected away from admin-only management pages", async ({ page }) => {
  await login(page, "demo_user_01", "User@123");

  await expect(page.getByTestId("live-input-editor")).toBeVisible();
  await expect(page.getByTestId("nav-admin-accounts")).toHaveCount(0);
  await page.goto("/admin/accounts");

  await expect(page).toHaveURL("http://localhost:5173/");
  await expect(page.getByTestId("pending-table")).toHaveCount(0);
});
