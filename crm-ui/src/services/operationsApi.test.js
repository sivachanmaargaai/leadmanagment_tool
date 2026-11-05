import assert from "node:assert/strict";
import test from "node:test";
import { getOperationsStatus } from "./operationsApi.js";
import { apiRequest } from "./apiClient.js";

test("operations status preserves Owner-only errors and validates monitoring payloads", async (t) => {
  const mock = t.mock.method(globalThis, "fetch", async () => new Response(JSON.stringify({ detail: "Owner only" }), { status: 403 }));
  await assert.rejects(getOperationsStatus(), (error) => error.status === 403);
  mock.mock.mockImplementation(async () => new Response(JSON.stringify({ status: "ok" })));
  await assert.rejects(getOperationsStatus(), /invalid status/);
});
test("server failure exposes a support request ID without retrying the mutation", async (t) => {
  let calls = 0;
  const id = "12345678-1234-4234-8234-123456789abc";
  t.mock.method(globalThis, "fetch", async () => { calls++; return new Response(JSON.stringify({ detail: "Server error" }), { status: 500, headers: { "X-Request-ID": id } }); });
  await assert.rejects(apiRequest("/api/leads", { method: "POST", body: "{}" }), (error) => error.requestId === id && error.message.includes(id));
  assert.equal(calls, 1);
});
