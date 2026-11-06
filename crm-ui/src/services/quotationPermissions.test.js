import assert from "node:assert/strict";
import test from "node:test";
import { canAccessQuotations } from "../lib/permissions.js";
import { getRolePermissions, saveStaffPermissions } from "./permissionsApi.js";
import { getReports } from "./reportsApi.js";
import { getSettings } from "./settingsApi.js";
import { defaultSettings } from "../lib/runtimeSettings.js";

test("Staff quotation access fails closed unless explicitly granted; Admins always retain access", () => {
  assert.equal(canAccessQuotations(null), false);
  assert.equal(canAccessQuotations({ role: "Staff" }), false);
  assert.equal(canAccessQuotations({ role: "Staff", canAccessQuotations: false }), false);
  assert.equal(canAccessQuotations({ role: "Staff", canAccessQuotations: true }), true);
  assert.equal(canAccessQuotations({ role: "Admin", canAccessQuotations: false }), true);
});

test("role permission updates send the shared Staff rule and opened role version", async (t) => {
  let request;
  const data = { version: 8, roles: { Admin: { quotations: true, readOnly: true }, Staff: { quotations: true, readOnly: false } } };
  t.mock.method(globalThis, "fetch", async (url, options) => { request = { url, ...options }; return new Response(JSON.stringify(data)); });
  await saveStaffPermissions(true, 7);
  assert.equal(request.url, "/api/permissions/staff");
  assert.equal(request.method, "PUT");
  assert.deepEqual(JSON.parse(request.body), { quotations: true, expectedVersion: 7 });
  assert.deepEqual(await getRolePermissions(), data);
});

test("disabled Staff report loading never requests the sales endpoint", async (t) => {
  const paths = [];
  t.mock.method(globalThis, "fetch", async (url) => {
    paths.push(url);
    return new Response(JSON.stringify({ filters: {}, totals: {}, rows: [] }));
  });
  const reports = await getReports({}, undefined, false);
  assert.equal(paths.length, 3);
  assert.equal(paths.some((path) => path.includes("/sales")), false);
  assert.equal(reports.sales, undefined);
});

test("redacted Staff settings are valid without quotation defaults", async (t) => {
  const settings = { ...defaultSettings(), canAccessQuotations: false };
  delete settings.quotation;
  t.mock.method(globalThis, "fetch", async () => new Response(JSON.stringify(settings)));
  const saved = await getSettings();
  assert.equal(saved.canAccessQuotations, false);
  assert.equal(saved.quotation, undefined);
});
