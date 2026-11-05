import assert from "node:assert/strict";
import test from "node:test";
import { apiRequest } from "./apiClient.js";

test("rate-limit response exposes a wait time without retrying requests or refreshing login", async (t) => {
  let calls = 0;
  t.mock.method(globalThis, "fetch", async () => { calls++; return new Response(JSON.stringify({ detail: "Too many requests." }), { status: 429, headers: { "Content-Type": "application/json", "Retry-After": "30" } }); });
  await assert.rejects(apiRequest("/api/leads"), (error) => error.status === 429 && error.retryAfter === 30 && /30 seconds/.test(error.message));
  assert.equal(calls, 1);
});
test("oversized request errors remain actionable and do not trigger automatic resubmission", async (t) => {
  t.mock.method(globalThis, "fetch", async () => new Response(JSON.stringify({ detail: "Request body is too large" }), { status: 413, headers: { "Content-Type": "application/json" } }));
  await assert.rejects(apiRequest("/api/leads", { method: "POST", body: "{}" }), (error) => error.status === 413 && /too large/.test(error.message));
});
