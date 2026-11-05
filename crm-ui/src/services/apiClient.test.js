import assert from "node:assert/strict";
import test from "node:test";
import { apiRequest } from "./apiClient.js";
import { createCustomer, customerPayload, getCustomers, updateCustomer } from "./customersApi.js";
import { createLead, deleteLead } from "./leadsApi.js";
import { createFollowUp, updateFollowUp } from "./followUpsApi.js";

test("customer DTO excludes server/computed fields and retains referral contacts", () => {
  const input = { id: "client", name: "Acme", contacts: [{ email: "hello@example.com" }],
    divisions: ["MMC"], assignedTo: "Admin", referredBy: { id: "ref", name: "Ramesh" },
    createdAt: "old", updatedAt: "old", stage: "Prospect", leadCount: 1 };
  const payload = customerPayload(input);
  assert.equal(payload.name, "Acme");
  assert.deepEqual(payload.referredBy, input.referredBy);
  for (const key of ["id", "createdAt", "updatedAt", "stage", "leadCount"]) assert.equal(key in payload, false);
});

test("customer create and update use the API with writable fields only", async (t) => {
  const calls = [];
  t.mock.method(globalThis, "fetch", async (url, options) => {
    calls.push({ url, options });
    return { ok: true, status: 200, json: async () => ({ id: "server-id", name: "Acme" }) };
  });
  await createCustomer({ id: "derived-id", name: "Acme", stage: "Prospect" });
  await updateCustomer("server-id", { id: "server-id", name: "Updated", leadCount: 4, version: 2 });
  assert.equal(calls[0].options.method, "POST");
  assert.equal(calls[1].options.method, "PUT");
  assert.match(calls[1].url, /\/api\/customers\/server-id$/);
  assert.deepEqual(JSON.parse(calls[0].options.body), { name: "Acme" });
  assert.deepEqual(JSON.parse(calls[1].options.body), { name: "Updated", expectedVersion: 2 });
});

test("lead requests omit client identity and accept an empty 204 delete response", async (t) => {
  const calls = [];
  t.mock.method(globalThis, "fetch", async (url, options) => {
    calls.push({ url, options });
    return options.method === "DELETE"
      ? { ok: true, status: 204 }
      : { ok: true, status: 201, json: async () => ({ id: "server-id" }) };
  });
  await createLead({ id: "client", createdAt: "old", updatedAt: "old", customer: "Acme" });
  assert.deepEqual(JSON.parse(calls[0].options.body), { customer: "Acme" });
  assert.equal(await deleteLead("server-id", 1), null);
});

test("validation failures surface field details and network failures remain actionable", async (t) => {
  const fetch = t.mock.method(globalThis, "fetch", async () => ({ ok: false, status: 422,
    json: async () => ({ detail: [{ loc: ["body", "contacts", 0, "email"], msg: "Invalid email" }] }) }));
  await assert.rejects(apiRequest("/api/customers"), /contacts\.0\.email: Invalid email/);
  fetch.mock.mockImplementation(async () => { throw new Error("offline"); });
  await assert.rejects(apiRequest("/api/customers"), /Cannot connect to backend/);
});

test("customer list rejects malformed successful responses", async (t) => {
  t.mock.method(globalThis, "fetch", async () => ({ ok: true, status: 200, json: async () => ({ invalid: true }) }));
  await assert.rejects(getCustomers(), /invalid list/);
});

test("follow-up create strips client history and completion uses one versioned request", async (t) => {
  const calls = [];
  t.mock.method(globalThis, "fetch", async (url, options) => {
    calls.push({ url, body: JSON.parse(options.body) });
    return { ok: true, status: 200, json: async () => ({ record: { id: "saved" } }) };
  });
  const record = { id: "client", leadId: "lead", purpose: "Call", dueAt: "2026-11-05T10:00:00Z", history: [{ message: "Client history" }], customer: "Acme" };
  await createFollowUp(record);
  assert.equal("id" in calls[0].body, false);
  assert.equal("history" in calls[0].body, false);
  await updateFollowUp({ ...record, version: 2, status: "Completed", outcome: "Connected", completionNotes: "Discussed" }, { dueAt: "2026-11-06T10:00:00Z" });
  assert.equal(calls.length, 2);
  assert.equal(calls[1].body.expectedVersion, 2);
  assert.equal(calls[1].body.nextDueAt, "2026-11-06T10:00:00Z");
  assert.equal("leadId" in calls[1].body, false);
});
