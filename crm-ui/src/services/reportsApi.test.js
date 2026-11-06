import assert from "node:assert/strict";
import test from "node:test";
import { getReport, getReports, reportQuery } from "./reportsApi.js";
import { csvText, datePreset } from "../lib/reports.js";

test("report queries apply only valid shared and module-specific filters", () => {
  const filters = { startDate: "2026-11-01", endDate: "2026-11-04", division: "nemilink", includeTestData: true, leadStatus: "Won", quoteStatus: "Accepted", followUpStatus: "Pending", refresh: 7 };
  assert.equal(new URLSearchParams(reportQuery(filters, "leads")).get("status"), "Won");
  assert.equal(new URLSearchParams(reportQuery(filters, "sales")).get("status"), "Accepted");
  assert.equal(new URLSearchParams(reportQuery(filters, "follow-ups")).get("status"), "Pending");
  assert.equal(new URLSearchParams(reportQuery(filters)).has("status"), false);
  assert.equal(new URLSearchParams(reportQuery(filters)).has("refresh"), false);
  assert.equal(new URLSearchParams(reportQuery({})).get("includeTestData"), "false");
});

test("frontend loads all four report APIs with cancellation support", async (t) => {
  const calls = [];
  const controller = new AbortController();
  t.mock.method(globalThis, "fetch", async (url, options) => {
    calls.push({ url, options });
    return new Response(JSON.stringify({ filters: {}, totals: {}, rows: [] }), { headers: { "content-type": "application/json" } });
  });
  const reports = await getReports({ division: "MMC" }, controller.signal);
  assert.equal(calls.length, 4);
  assert.deepEqual(Object.keys(reports), ["summary", "leads", "sales", "follow-ups"]);
  assert.ok(calls.every((call) => call.options.signal === controller.signal && call.url.includes("division=MMC")));
});

test("frontend surfaces report validation, network and malformed-response errors", async (t) => {
  const fetch = t.mock.method(globalThis, "fetch", async () => new Response(JSON.stringify({ detail: "Invalid range" }), { status: 422 }));
  await assert.rejects(getReport("leads"), /Invalid range/);
  fetch.mock.mockImplementation(async () => new Response(JSON.stringify({ wrong: true })));
  await assert.rejects(getReport("sales"), /invalid response/);
  fetch.mock.mockImplementation(async () => { throw new Error("offline"); });
  await assert.rejects(getReport("follow-ups"), /Cannot connect/);
  await assert.rejects(getReport("unknown"), /Unknown report/);
});

test("date presets use IST and Monday-based week boundaries", () => {
  const at = new Date("2026-11-03T20:00:00Z");
  assert.deepEqual(datePreset("today", at), { startDate: "2026-11-04", endDate: "2026-11-04" });
  assert.deepEqual(datePreset("week", at), { startDate: "2026-11-02", endDate: "2026-11-04" });
  assert.deepEqual(datePreset("month", at), { startDate: "2026-11-01", endDate: "2026-11-04" });
  assert.deepEqual(datePreset("all", at), { startDate: "", endDate: "" });
  assert.equal(datePreset("custom", at), null);
});

test("CSV export preserves quotes and multiline values and neutralizes spreadsheet formulas", () => {
  const text = csvText([{ key: "name", label: "Customer" }, { key: "value", label: "Amount", exportValue: (x) => `${x.value} INR` }],
    [{ name: '=HYPERLINK("bad")', value: 100 }, { name: 'Line 1\n"Line 2"', value: 50 }]);
  assert.ok(text.startsWith("\uFEFF"));
  assert.ok(text.includes("'=HYPERLINK"));
  assert.ok(text.includes('"Line 1\n""Line 2"""'));
  assert.ok(text.includes('"100 INR"'));
});
