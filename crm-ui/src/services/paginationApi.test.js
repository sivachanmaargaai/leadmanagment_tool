import assert from "node:assert/strict";
import test from "node:test";
import { getCompleteList, getListPage, listQuery, requireVersion } from "./paginationApi.js";
import { updateLead, deleteLead } from "./leadsApi.js";
import { updateCustomer } from "./customersApi.js";

const json = (data, status = 200) => new Response(JSON.stringify(data), { status, headers: { "Content-Type": "application/json" } });
const page = (items, number, total, hasMore) => ({ items, page: number, pageSize: 100, total, pages: Math.max(1, Math.ceil(total / 100)), hasMore });

test("page queries encode server filters and skip UI-only all filters", () => {
  const query = new URLSearchParams(listQuery({ q: "IoT & 10%", division: "All divisions", page: 2, pageSize: 25, priority: "High" }));
  assert.equal(query.get("q"), "IoT & 10%");
  assert.equal(query.get("division"), null);
  assert.equal(query.get("pageSize"), "25");
  assert.equal(query.get("paged"), "true");
  assert.equal(new URLSearchParams(listQuery({ q: "All firmware" })).get("q"), "All firmware");
});
test("complete consumers load all bounded pages without truncating dashboard data", async (t) => {
  const calls = [];
  t.mock.method(globalThis, "fetch", async (url) => { calls.push(url); return json(calls.length === 1 ? page(Array.from({ length: 100 }, (_, i) => ({ id: String(i) })), 1, 101, true) : page([{ id: "100" }], 2, 101, false)); });
  assert.equal((await getCompleteList("/api/leads")).length, 101);
  assert.match(calls[1], /page=2/);
});
test("malformed or changing pages fail instead of returning partial totals", async (t) => {
  let calls = 0;
  const mock = t.mock.method(globalThis, "fetch", async () => json(++calls === 1 ? page([{ id: "a" }], 1, 2, true) : page([{ id: "b" }], 2, 3, false)));
  await assert.rejects(getCompleteList("/api/leads"), /changed while loading/);
  mock.mock.mockImplementation(async () => json({ items: [] }));
  await assert.rejects(getListPage("/api/leads"), /invalid list page/);
});
test("lead/customer mutations send the version originally opened and never fetch a fresh version to overwrite", async (t) => {
  const calls = [];
  t.mock.method(globalThis, "fetch", async (url, options) => { calls.push({ url, options }); return json({ detail: "Reload record" }, 409); });
  await assert.rejects(updateLead("lead", { priority: "High", expectedVersion: 3 }), (error) => error.status === 409);
  await assert.rejects(updateCustomer("customer", { notes: "Changed", version: 7 }), (error) => error.status === 409);
  assert.equal(JSON.parse(calls[0].options.body).expectedVersion, 3);
  assert.equal(JSON.parse(calls[1].options.body).expectedVersion, 7);
  assert.equal(calls.length, 2);
  assert.throws(() => deleteLead("id"), /Reload/);
  assert.throws(() => requireVersion(0), /Reload/);
});
