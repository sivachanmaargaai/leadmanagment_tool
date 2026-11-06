import { expect, test } from "@playwright/test";
import { mockCrm } from "./fixtures.js";

async function navigate(page, name) {
  const opener = page.getByRole("button", { name: "Open navigation", exact: true });
  if (await opener.isVisible()) await opener.click();
  await page.locator('aside[aria-label="Workspace navigation"]').getByRole("button", { name, exact: true }).click();
  if (page.viewportSize().width >= 1024) await expect(page.locator('aside[aria-label="Workspace navigation"]')).toHaveAttribute("data-expanded", "false");
}

async function noHorizontalOverflow(page) {
  await expect.poll(() => page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth)).toBeLessThanOrEqual(1);
}

async function settingsTab(page, name) {
  if (page.viewportSize().width < 1024) await page.getByRole("combobox", { name: "Settings section", exact: true }).selectOption({ label: name });
  else await page.getByRole("navigation", { name: "Settings sections" }).getByRole("button", { name, exact: true }).click();
}

for (const viewport of [{ width: 320, height: 740 }, { width: 375, height: 812 }, { width: 768, height: 1024 }, { width: 1024, height: 768 }, { width: 1440, height: 1000 }]) {
  test(`Settings and main registers fit ${viewport.width}px`, async ({ page }, testInfo) => {
    await page.setViewportSize(viewport);
    const errors = await mockCrm(page);
    await page.goto("/");
    await expect(page.getByRole("heading", { name: "Workspace overview", exact: true })).toBeVisible();
    await navigate(page, "Settings");
    await settingsTab(page, "Users & access");
    await expect(page.getByRole("heading", { name: "CRM record access", exact: true })).toBeVisible();
    const assignments = page.locator("section").filter({ has: page.getByRole("heading", { name: "CRM record access", exact: true }) }).last();
    const navBox = viewport.width >= 1024 ? await page.getByRole("navigation", { name: "Settings sections" }).boundingBox() : null;
    const box = await assignments.boundingBox();
    expect(box.width).toBeGreaterThan(viewport.width >= 1024 ? 400 : viewport.width - 90);
    if (viewport.width >= 1024) expect(box.x).toBeGreaterThan(navBox.x + navBox.width);
    await noHorizontalOverflow(page);
    await page.screenshot({ path: testInfo.outputPath(`settings-users-${viewport.width}.png`), fullPage: true });
    for (const name of ["My profile", "Company & divisions", "Lead settings", "Products & quotations", "Roles & permissions", "Notifications", "Workspace"]) {
      await settingsTab(page, name);
      await noHorizontalOverflow(page);
    }
    for (const name of ["Leads", "Customers", "Follow-ups", "Quotations", "Reports"]) {
      await navigate(page, name);
      await expect(page.getByRole("heading", { name, exact: true }).first()).toBeVisible();
      await noHorizontalOverflow(page);
    }
    expect(errors).toEqual([]);
  });
}

test("desktop sidebar consistently expands, collapses and supports keyboard", async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 900 });
  const errors = await mockCrm(page);
  await page.goto("/");
  const sidebar = page.getByRole("complementary", { name: "Workspace navigation" });
  await expect(sidebar).toHaveAttribute("data-expanded", "false");
  for (let i = 0; i < 4; i++) {
    await page.mouse.move(25, 250);
    await expect(sidebar).toHaveAttribute("data-expanded", "true");
    await page.mouse.move(600, 200);
    await expect(sidebar).toHaveAttribute("data-expanded", "false");
  }
  await sidebar.getByRole("button", { name: "Leads", exact: true }).focus();
  await page.keyboard.press("Tab");
  await expect(sidebar).toHaveAttribute("data-expanded", "true");
  await page.keyboard.press("Escape");
  await expect(sidebar).toHaveAttribute("data-expanded", "false");
  await noHorizontalOverflow(page);
  expect(errors).toEqual([]);
});

for (const width of [375, 768, 1440]) {
  test(`Forms and notifications remain inside the ${width}px viewport`, async ({ page }) => {
    await page.setViewportSize({ width, height: 900 });
    const errors = await mockCrm(page);
    await page.goto("/");
    await expect(page.getByRole("heading", { name: "Workspace overview", exact: true })).toBeVisible();
    for (const [destination, button] of [["Dashboard", "Add lead"], ["Customers", "Add customer"], ["Follow-ups", "Schedule follow-up"], ["Quotations", "Create quotation"]]) {
      if (destination !== "Dashboard") await navigate(page, destination);
      await page.getByRole("button", { name: button, exact: true }).click();
      const dialog = page.getByRole("dialog");
      await expect(dialog).toBeVisible();
      const box = await dialog.boundingBox();
      expect(box.x).toBeGreaterThanOrEqual(0);
      expect(box.x + box.width).toBeLessThanOrEqual(width + 1);
      expect(box.height).toBeLessThanOrEqual(900);
      expect(await dialog.evaluate((element) => element.scrollWidth - element.clientWidth)).toBeLessThanOrEqual(1);
      await page.keyboard.press("Escape");
      await expect(dialog).toHaveCount(0);
    }
    await navigate(page, "Settings");
    await settingsTab(page, "Users & access");
    await page.getByRole("button", { name: "Add login account", exact: true }).click();
    await expect(page.getByRole("dialog")).toBeVisible();
    expect(await page.getByRole("dialog").evaluate((element) => element.scrollWidth - element.clientWidth)).toBeLessThanOrEqual(1);
    await page.keyboard.press("Escape");
    await page.locator('button[aria-label="Notifications"]').click();
    const popover = page.locator("section").filter({ has: page.getByText("Needs attention", { exact: true }) }).last();
    const box = await popover.boundingBox();
    expect(box.x).toBeGreaterThanOrEqual(0);
    expect(box.x + box.width).toBeLessThanOrEqual(width + 1);
    await page.getByRole("button", { name: "Close notifications", exact: true }).click();
    await noHorizontalOverflow(page);
    expect(errors).toEqual([]);
  });
}

test("always-expanded desktop preference retains the content gutter", async ({ page }) => {
  await page.setViewportSize({ width: 1024, height: 900 });
  await mockCrm(page, { sidebar: "Always expanded" });
  await page.goto("/");
  const sidebar = page.locator('aside[aria-label="Workspace navigation"]');
  await expect(sidebar).toHaveAttribute("data-expanded", "true");
  await page.mouse.move(800, 200);
  await expect(sidebar).toHaveAttribute("data-expanded", "true");
  const content = await page.locator("main").first().boundingBox();
  expect(content.x).toBeGreaterThanOrEqual(239);
  await noHorizontalOverflow(page);
});

test("mobile navigation traps focus, closes with Escape and restores body scroll", async ({ page }) => {
  await page.setViewportSize({ width: 375, height: 812 });
  await mockCrm(page);
  await page.goto("/");
  const opener = page.getByRole("button", { name: "Open navigation", exact: true });
  await opener.click();
  const drawer = page.getByRole("dialog", { name: "Workspace navigation" });
  await expect(drawer).toBeVisible();
  await expect.poll(() => page.evaluate(() => document.body.style.overflow)).toBe("hidden");
  await drawer.getByRole("button", { name: "Settings", exact: true }).focus();
  await page.keyboard.press("Tab");
  await expect(drawer.getByRole("button", { name: "Close navigation", exact: true })).toBeFocused();
  await page.keyboard.press("Shift+Tab");
  await expect(drawer.getByRole("button", { name: "Settings", exact: true })).toBeFocused();
  await page.keyboard.press("Escape");
  await expect(opener).toBeFocused();
  await expect.poll(() => page.evaluate(() => document.body.style.overflow)).not.toBe("hidden");
  await noHorizontalOverflow(page);
});

test.describe("landscape tablet touch navigation", () => {
  test.use({ hasTouch: true, viewport: { width: 1024, height: 768 } });
  test("touch toggle opens and selecting a page closes the desktop-width rail", async ({ page }) => {
    await mockCrm(page);
    await page.goto("/");
    const sidebar = page.locator('aside[aria-label="Workspace navigation"]');
    await expect(sidebar).toHaveAttribute("data-expanded", "false");
    await sidebar.getByRole("button", { name: "Toggle navigation width", exact: true }).tap();
    await expect(sidebar).toHaveAttribute("data-expanded", "true");
    await sidebar.getByRole("button", { name: "Collapse navigation", exact: true }).tap();
    await expect(sidebar).toHaveAttribute("data-expanded", "false");
    await sidebar.getByRole("button", { name: "Toggle navigation width", exact: true }).tap();
    await sidebar.getByRole("button", { name: "Customers", exact: true }).tap();
    await expect(sidebar).toHaveAttribute("data-expanded", "false");
    await expect(page.getByRole("heading", { name: "Customers", exact: true })).toBeVisible();
    await noHorizontalOverflow(page);
  });
});
