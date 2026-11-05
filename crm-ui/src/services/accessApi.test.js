import assert from "node:assert/strict";
import test from "node:test";
import { assignRecord, getAssignments } from "./accessApi.js";

const json = (data, status = 200) => new Response(JSON.stringify(data), { status, headers: { "Content-Type": "application/json" } });
test("assignments use paginated API reads and stable IDs with conflict protection", async (t) => {
  const calls = [];
  t.mock.method(globalThis, "fetch", async (url, options) => { calls.push({ url, options }); return json({ users: [], records: [], hasMore: false }); });
  await getAssignments("leads", 25);
  await assignRecord("leads", { id: "lead/1", assigneeUserId: "old-user", version: 3 }, "new-user");
  assert.match(calls[0].url, /module=leads&offset=25&limit=25/);
  assert.match(calls[1].url, /lead%2F1$/);
  assert.deepEqual(JSON.parse(calls[1].options.body), { assigneeUserId: "new-user", expectedAssigneeUserId: "old-user", expectedVersion: 3 });
});
test("unassignment sends explicit null and permission errors remain visible", async (t) => {
  let body;
  t.mock.method(globalThis, "fetch", async (_url, options) => { body = JSON.parse(options.body); return json({ detail: "Admin only" }, 403); });
  await assert.rejects(assignRecord("customers", { id: "id", assigneeUserId: "old", version: 1 }, ""), (error) => error.status === 403);
  assert.equal(body.assigneeUserId, null);
});
test("malformed assignment directory fails instead of showing an empty success", async (t) => {
  t.mock.method(globalThis, "fetch", async () => json({ records: [] }));
  await assert.rejects(getAssignments("quotations"), /invalid response/);
});
