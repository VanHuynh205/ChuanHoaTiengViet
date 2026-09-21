import { expect, test } from "@playwright/test";

test("admin save refreshes two existing sessions even if JSON export fails", async ({ browser, request }) => {
  const contexts = [];
  try {
    for (const admin of [false, false, true]) {
      const context = await browser.newContext();
      contexts.push(context);
      const session = await (await request.get(`http://127.0.0.1:8018/__test/session?admin=${admin}`)).json();
      await context.addInitScript(session => {
        sessionStorage.setItem("viet-normalizer-session", JSON.stringify(session));
      }, session);
    }
    const pages = await Promise.all(contexts.map(context => context.newPage()));
    for (const page of pages.slice(0, 2)) {
      await page.goto("http://127.0.0.1:5188/");
      await page.getByTestId("live-input-editor").fill("hôm nay dk học phần");
      await expect(page.getByTestId("primary-output")).toContainText("đăng ký");
    }
    const admin = pages[2];
    await admin.goto("http://127.0.0.1:5188/dictionary");
    await admin.getByRole("button", { name: /dk/i }).click();
    await request.post("http://127.0.0.1:8018/__test/export-failure");
    await admin.getByTestId("dictionary-expanded-input").fill("điều kiện");
    await admin.getByTestId("dictionary-submit").click();
    await expect(admin.getByText(/Đã lưu vào SQL/)).toBeVisible();
    for (const page of pages.slice(0, 2)) {
      await expect(page.getByTestId("primary-output")).toContainText("điều kiện", { timeout: 10000 });
      await expect(page.getByTestId("primary-output")).not.toContainText("đăng ký");
    }
    await admin.reload();
    await expect(admin.getByText(/Đã lưu vào SQL/)).toBeVisible();
    await request.post("http://127.0.0.1:8018/__test/export-failure?enabled=false");
    await admin.getByRole("button", { name: "Thử đồng bộ JSON lại" }).click();
    await expect(admin.getByText(/Đã lưu vào SQL/)).not.toBeVisible();
  } finally {
    await Promise.all(contexts.map(context => context.close()));
  }
});
