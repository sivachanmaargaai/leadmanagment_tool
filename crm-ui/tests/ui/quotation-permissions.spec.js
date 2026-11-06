import { expect, test } from "@playwright/test";
import { mockCrm, owner, staff } from "./fixtures.js";

async function navigate(page, name) {
  const opener = page.getByRole("button", { name: "Open navigation", exact: true });
  if (await opener.isVisible()) await opener.click();
  await page.locator('aside[aria-label="Workspace navigation"]').getByRole("button", { name, exact: true }).click();
}

for (const width of [375, 1440]) {
  test(`disabled Staff cannot see or load quotations at ${width}px`, async ({ page }) => {
    await page.setViewportSize({ width, height: 900 });
    const errors = await mockCrm(page, {}, staff);
    const quoteRequests = [];
    page.on("request", (request) => { const url = new URL(request.url()); if (url.pathname.startsWith("/api/quotations") || url.pathname === "/api/reports/sales") quoteRequests.push(url.pathname); });
    await page.goto("/");
    await expect(page.getByRole("heading", { name: "Workspace overview", exact: true })).toBeVisible();
    expect(await page.locator('aside[aria-label="Workspace navigation"]').getByRole("button", { name: "Quotations", exact: true }).count()).toBe(0);
    await navigate(page, "Reports");
    await expect(page.getByRole("tab", { name: "Leads", exact: true })).toBeVisible();
    await expect(page.getByRole("tab", { name: "Quotations", exact: true })).toHaveCount(0);
    await expect(page.getByRole("heading", { name: "Accepted quotation value", exact: true })).toHaveCount(0);
    await navigate(page, "Customers");
    await page.getByRole("button", { name: /^View / }).first().click();
    await expect(page.getByRole("dialog", { name: "Customer details" })).toBeVisible();
    await expect(page.getByRole("navigation", { name: "Customer detail sections" }).getByRole("button", { name: "Quotations", exact: true })).toHaveCount(0);
    await page.keyboard.press("Escape");
    await navigate(page, "Settings");
    if (width < 1024) await expect(page.getByRole("combobox", { name: "Settings section" }).locator('option[value="quotation"]')).toHaveCount(0);
    else await expect(page.getByRole("navigation", { name: "Settings sections" }).getByRole("button", { name: "Products & quotations", exact: true })).toHaveCount(0);
    expect(quoteRequests).toEqual([]);
    expect(errors).toEqual([]);
  });
}

test("enabled Staff sees the quotation register", async ({ page }) => {
  const errors = await mockCrm(page, {}, { ...staff, canAccessQuotations: true });
  await page.goto("/");
  await navigate(page, "Quotations");
  await expect(page.getByRole("heading", { name: "Quotation register", exact: true })).toBeVisible();
  expect(errors).toEqual([]);
});

for (const isOwner of [true, false]) {
  test(`${isOwner ? "Owner" : "Second Admin"} saves common Staff checkbox permissions in a separate tab`, async ({ page }) => {
    const admin = isOwner ? owner : { ...owner, id: "second-admin", isOwner: false };
    const errors = await mockCrm(page, {}, admin);
    let permissions = { version: 1, roles: { Admin: { quotations: true, readOnly: true }, Staff: { quotations: false, readOnly: false } } };
    const updates = [];
    await page.route("**/api/permissions", (route) => route.fulfill({ json: permissions }));
    await page.route("**/api/permissions/staff", async (route) => {
      const data = route.request().postDataJSON(); updates.push(data);
      permissions = { ...permissions, version: permissions.version + 1, roles: { ...permissions.roles, Staff: { quotations: data.quotations, readOnly: false } } };
      await route.fulfill({ json: permissions });
    });
    await page.goto("/"); await navigate(page, "Settings");
    const sections = page.getByRole("navigation", { name: "Settings sections" });
    await sections.getByRole("button", { name: "Users & access", exact: true }).click();
    await expect(page.getByRole("switch", { name: /Quotations access for/ })).toHaveCount(0);
    await sections.getByRole("button", { name: "Roles & permissions", exact: true }).click();
    const checkbox = page.getByRole("checkbox", { name: /^Quotations/ });
    await expect(checkbox).not.toBeChecked();
    await expect(page.getByRole("checkbox", { name: "Full access", exact: true })).toBeChecked();
    await expect(page.getByRole("checkbox", { name: "Full access", exact: true })).toBeDisabled();
    await checkbox.check(); expect(updates).toEqual([]);
    await page.getByRole("button", { name: "Save permissions", exact: true }).click();
    await expect(page.getByText("Staff permissions saved.", { exact: false })).toBeVisible();
    await sections.getByRole("button", { name: "My profile", exact: true }).click();
    await sections.getByRole("button", { name: "Roles & permissions", exact: true }).click();
    await expect(checkbox).toBeChecked();
    await checkbox.uncheck(); await page.getByRole("button", { name: "Save permissions", exact: true }).click();
    await expect(page.getByText("Staff permissions saved.", { exact: false })).toBeVisible();
    expect(updates).toEqual([{ quotations: true, expectedVersion: 1 }, { quotations: false, expectedVersion: 2 }]);
    expect(errors).toEqual([]);
  });
}
