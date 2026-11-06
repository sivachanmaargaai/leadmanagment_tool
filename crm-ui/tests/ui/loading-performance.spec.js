import { expect, test } from "@playwright/test";
import { mockCrm } from "./fixtures.js";

test("slow roster never blocks the workspace and Settings reuses its saved snapshot", async ({ page }) => {
  const errors = await mockCrm(page);
  let settingsRequests = 0;
  page.on("request", (request) => { if (new URL(request.url()).pathname === "/api/settings") settingsRequests++; });
  let releaseRoster;
  const roster = new Promise((resolve) => { releaseRoster = resolve; });
  await page.route("**/api/users", async (route) => { await roster; await route.fallback(); });
  try {
    await page.goto("/");
    await expect(page.getByRole("heading", { name: "Workspace overview", exact: true })).toBeVisible();
    expect(settingsRequests).toBe(1);
    const sidebar = page.locator('aside[aria-label="Workspace navigation"]');
    await sidebar.getByRole("button", { name: "Settings", exact: true }).click();
    await expect(page.getByRole("heading", { name: "My profile", exact: true })).toBeVisible();
    expect(settingsRequests).toBe(1);
    await expect(page.getByText("Loading saved settings...", { exact: true })).toHaveCount(0);
    await sidebar.getByRole("button", { name: "Dashboard", exact: true }).click();
    await sidebar.getByRole("button", { name: "Settings", exact: true }).click();
    await expect(page.getByRole("heading", { name: "My profile", exact: true })).toBeVisible();
    expect(settingsRequests).toBe(1);
    await page.getByRole("button", { name: "Reload saved settings", exact: true }).click();
    await expect(page.getByText("Saved settings reloaded.", { exact: true })).toBeVisible();
    expect(settingsRequests).toBe(2);
  } finally { releaseRoster(); }
  expect(errors).toEqual([]);
});
