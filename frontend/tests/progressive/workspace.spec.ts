import { expect, test } from "@playwright/test";

test("dataset, chunk progress, copy and current input stay consistent", async ({ page, request }, testInfo) => {
  const session = await (await request.get("http://127.0.0.1:8016/__test/session")).json();
  await page.addInitScript((session) => {
    sessionStorage.setItem("viet-normalizer-session", JSON.stringify(session));
    Object.defineProperty(navigator, "clipboard", { value: {
      writeText: async (text: string) => { (window as unknown as { copied: string }).copied = text; },
    } });
  }, session);
  await page.goto("/");
  const input = page.getByTestId("live-input-editor");
  await expect(input).toBeVisible();
  await page.getByTestId("ai-consent").getByRole("checkbox").check();
  const source = `dk hôm nay đi học nhé bạn ${testInfo.project.name} ${Date.now()}.\n\ndk ngày mai đi học nhé bạn ơi.`;
  await input.fill(source);
  const output = page.getByTestId("primary-output");
  await expect(output).toContainText(/dk/i, { timeout: 3000 });
  await expect(page.getByText(/AI: Đã kiểm tra một phần/)).toBeVisible({ timeout: 10000 });
  await page.screenshot({ path: testInfo.outputPath("progress.png"), fullPage: true });
  await page.getByRole("button", { name: "Sao chép kết quả chuẩn hóa", exact: true }).click();
  await expect(output).toHaveCSS("white-space", "pre-wrap");
  const copied = await page.evaluate(() => (window as unknown as { copied: string }).copied);
  expect(copied).toContain("\n\n");
  expect(copied.toLowerCase()).toContain("đăng ký");
  await expect(output).not.toContainText(/\bdk\b/i, { timeout: 15000 });
  await input.fill("dk mới");
  await expect(output).not.toContainText("ngày mai", { timeout: 3000 });
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth > innerWidth);
  expect(overflow).toBe(false);
  await page.screenshot({ path: testInfo.outputPath("current-input.png"), fullPage: true });
});

test("leaving during AI saves a partial result for the exact input", async ({ page, request }, testInfo) => {
  const session = await (await request.get("http://127.0.0.1:8016/__test/session")).json();
  await page.addInitScript((session) => sessionStorage.setItem("viet-normalizer-session", JSON.stringify(session)), session);
  await page.goto("/");
  await page.getByTestId("ai-consent").getByRole("checkbox").check();
  const source = `dk hôm nay nhé ${testInfo.project.name} ${Date.now()}.\n\ndk ngày mai nhé.`;
  await page.getByTestId("live-input-editor").fill(source);
  await expect(page.getByTestId("semantic-status")).toContainText("một phần", { timeout: 10000 });
  const save = page.waitForRequest((req) => req.url().endsWith("/api/history") && req.method() === "POST");
  await page.getByTestId("nav-history").click();
  const payload = (await save).postDataJSON();
  expect(payload.input_text).toBe(source);
  expect(payload.output_text).toContain("\n\n");
  expect(payload.source_kind).toBe("web_live_partial");
});
