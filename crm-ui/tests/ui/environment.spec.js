import { expect, test } from "@playwright/test";
import { mockCrm } from "./fixtures.js";

test("development ignores stale cloud API settings and uses the local origin", async ({ page }) => {
  const errors = await mockCrm(page);
  const origins = [];
  page.on("request", (request) => {
    const url = new URL(request.url());
    if (url.pathname.startsWith("/api/")) origins.push(url.origin);
  });
  await page.goto("/");
  await expect(page.getByRole("heading", { name: "Workspace overview", exact: true })).toBeVisible();
  await expect(page.getByText("Total leads", { exact: true })).toBeVisible();
  expect(origins.length).toBeGreaterThan(0);
  expect([...new Set(origins)]).toEqual(["http://127.0.0.1:5174"]);
  expect(errors).toEqual([]);
});
