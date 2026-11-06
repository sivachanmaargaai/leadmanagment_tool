import assert from "node:assert/strict";
import test from "node:test";
import { changePassword, getSettings, settingsPayload } from "./settingsApi.js";
import { defaultSettings, displayDate, runtimeSettings, setRuntimeSettings, staffNames } from "../lib/runtimeSettings.js";
import { notificationAlerts } from "../lib/notificationAlerts.js";

test("personal settings payload cannot modify shared settings or login email", () => {
  const settings = defaultSettings();
  settings.profile = { name: "Staff", email: "staff@example.test", phone: "QA", designation: "Engineer" };
  const payload = settingsPayload(settings);
  assert.equal(payload.company, undefined);
  assert.equal(payload.profile.email, undefined);
  assert.equal(payload.expectedPersonalVersion, 0);
  assert.equal(payload.profile.name, "Staff");
});

test("Owner payload normalizes numeric settings, sources and concurrency versions", () => {
  const settings = defaultSettings();
  settings.canManageShared = true;
  settings.leads.sources = "Website, Partner, Referral";
  settings.quotation.tax = "18.50";
  settings.quotation.nextNumber = "1234";
  settings.workspace.rowsPerPage = "25";
  const payload = settingsPayload(settings);
  assert.deepEqual(payload.leads.sources, ["Website", "Partner", "Referral"]);
  assert.equal(payload.quotation.tax, 18.5);
  assert.equal(payload.quotation.nextNumber, 1234);
  assert.equal(payload.workspace.rowsPerPage, 25);
  assert.equal(payload.expectedSharedVersion, 1);
});

test("runtime preferences supply dates and real staff names without browser storage", () => {
  const settings = defaultSettings();
  settings.profile.name = "Owner";
  settings.workspace.dateFormat = "YYYY-MM-DD";
  setRuntimeSettings(settings, ["Staff", "Owner"]);
  assert.equal(displayDate("2026-11-03T20:00:00Z"), "2026-11-04");
  settings.workspace.dateFormat = "DD/MM/YYYY";
  assert.equal(displayDate("2026-11-03T20:00:00Z"), "04/11/2026");
  assert.deepEqual(staffNames(), ["Owner", "Staff"]);
  assert.equal(runtimeSettings().workspace.dateFormat, "DD/MM/YYYY");
  setRuntimeSettings(defaultSettings(), []);
});

test("notification toggles independently control overdue, reminders, priority and expiry", () => {
  const preferences = defaultSettings().notifications;
  const now = Date.parse("2026-11-04T10:00:00Z");
  const input = {
    division: "All divisions", now, notifications: preferences,
    leads: [{ id: "L1", customer: "QA", division: "MMC", priority: "High", status: "New" }],
    followUps: [{ id: "F1", customer: "QA", division: "MMC", status: "Pending", dueAt: new Date(now - 1).toISOString() },
    { id: "F2", customer: "QA", division: "MMC", status: "Pending", dueAt: new Date(now + 1000).toISOString(), reminderMinutes: 30 }],
    quotes: [{ id: "Q1", number: "Q1", customer: "QA", division: "MMC", status: "Sent", validUntil: "2026-11-05" }]
  };
  assert.equal(notificationAlerts(input).length, 4);
  assert.deepEqual(notificationAlerts({ ...input, notifications: { ...preferences, overdue: false, quotationExpiry: false, leadPriority: false } }).map((x) => x.id), ["followup-F2"]);
  assert.equal(notificationAlerts({ ...input, division: "nemilink" }).length, 0);
});

test("settings API errors are actionable and password change never sends confirmation fields", async (t) => {
  const fetch = t.mock.method(globalThis, "fetch", async () => new Response(JSON.stringify({ invalid: true })));
  await assert.rejects(getSettings(), /invalid response/);
  let body;
  fetch.mock.mockImplementation(async (_url, options) => { body = JSON.parse(options.body); return new Response(null, { status: 204 }); });
  await changePassword("oldpass8", "newpass8");
  assert.deepEqual(body, { currentPassword: "oldpass8", newPassword: "newpass8" });
});
