import { expect, test } from "@playwright/test";
import { mockCrm, customer, quote, followUp } from "./fixtures.js";

async function navigate(page, name) {
  const opener = page.getByRole("button", { name: "Open navigation", exact: true });
  if (await opener.isVisible()) await opener.click();
  await page.locator('aside[aria-label="Workspace navigation"]').getByRole("button", { name, exact: true }).click();
}

for (const [module, title, seed] of [["customers", "Customers", customer], ["quotations", "Quotations", quote], ["follow-ups", "Follow-ups", followUp]]) {
  test(`${title} loads one bounded page and searches on the server`, async ({ page }) => {
    const errors = await mockCrm(page);
    const requests = [];
    await page.route(new RegExp(`/api/${module}\\?`), async (route) => {
      const params = new URL(route.request().url()).searchParams;
      requests.push(Object.fromEntries(params));
      const number = Number(params.get("page")), size = Number(params.get("pageSize"));
      expect(size).toBeLessThanOrEqual(100);
      const total = params.get("q") ? 1 : 10000;
      const items = Array.from({ length: Math.min(size, Math.max(0, total - (number - 1) * size)) }, (_, index) => ({ ...seed, id: `large-${number}-${index}`, customerId: customer.id }));
      await route.fulfill({ json: { items, total, page: number, pageSize: size, pages: Math.max(1, Math.ceil(total / size)), hasMore: number * size < total } });
    });
    await page.goto("/");
    await expect(page.getByRole("heading", { name: "Workspace overview", exact: true })).toBeVisible();
    expect(requests).toHaveLength(0);
    await navigate(page, title);
    await expect(page.getByText("10000 records", { exact: false })).toBeVisible();
    expect(requests).toHaveLength(1);
    expect(requests[0].page).toBe("1");
    if (module === "quotations") expect(requests[0].summary).toBe("true");
    await page.getByRole("button", { name: "Next", exact: true }).click();
    await expect.poll(() => requests.length).toBe(2);
    expect(requests[1].page).toBe("2");
    await page.getByRole("textbox", { name: `Search ${title.toLowerCase()}`, exact: true }).fill("Firmware");
    await expect.poll(() => requests.at(-1)?.q).toBe("Firmware");
    await expect(page.getByText("1 records", { exact: false })).toBeVisible();
    expect(requests.at(-1).page).toBe("1");
    expect(requests).toHaveLength(3);
    expect(errors).toEqual([]);
  });
}

test("customer and lead pickers search bounded results on demand", async ({ page }) => {
  const errors = await mockCrm(page);
  const requests = [];
  page.on("request", (request) => { const url = new URL(request.url()); if (["/api/leads", "/api/customers"].includes(url.pathname)) requests.push(url); });
  await page.goto("/");
  await page.getByRole("button", { name: "Add lead", exact: true }).click();
  expect(requests).toHaveLength(0);
  await page.getByRole("button", { name: "Select customer profile", exact: true }).click();
  await expect(page.getByRole("textbox", { name: "Search customers", exact: true })).toBeVisible();
  await expect.poll(() => requests.length).toBe(1);
  expect(requests[0].searchParams.get("pageSize")).toBe("20");
  await page.getByRole("button", { name: new RegExp(`ID: ${customer.id}`) }).click();
  await expect(page.getByRole("textbox", { name: "Customer / company name" })).toHaveValue(customer.name);
  await expect(page.getByText("Linked:", { exact: false })).toBeVisible();
  await page.getByRole("textbox", { name: "Customer / company name" }).fill("A different enquiry");
  await expect(page.getByText("Unlinked enquiry.", { exact: false })).toBeVisible();
  await page.keyboard.press("Escape");
  await navigate(page, "Follow-ups");
  await page.getByRole("button", { name: "Schedule follow-up", exact: true }).click();
  await page.getByRole("button", { name: "Select lead profile", exact: true }).click();
  await expect.poll(() => requests.filter((url) => url.pathname === "/api/leads").length).toBe(1);
  expect(requests.at(-1).searchParams.get("pageSize")).toBe("20");
  expect(errors).toEqual([]);
});

test("unavailable overview displays an error instead of false zero totals", async ({ page }) => {
  await mockCrm(page);
  await page.route("**/api/workspace/overview?**", (route) => route.fulfill({ status: 503, json: { detail: "Workspace summary temporarily unavailable" } }));
  await page.goto("/");
  await expect(page.getByRole("alert")).toContainText("Workspace summary temporarily unavailable");
  await expect(page.getByText("Total leads", { exact: true })).toHaveCount(0);
});
