import assert from "node:assert/strict";
import test from "node:test";
import { createUser, getUsers, updateUser } from "./usersApi.js";

test("user directory preserves server-controlled scope and management capability", async (t) => {
  const directory = { users: [{ id: "owner", isOwner: true, role: "Admin" }], canManageUsers: true, adminCount: 1, adminLimit: 2, scope: "All accounts" };
  t.mock.method(globalThis, "fetch", async () => new Response(JSON.stringify(directory)));
  assert.deepEqual(await getUsers(), directory);
});

test("creating a login sends only allowed fields and defaults to Staff", async (t) => {
  let request;
  t.mock.method(globalThis, "fetch", async (url, options) => { request = { url, options }; return new Response(JSON.stringify({ id: "staff" })); });
  await createUser({ id: "client", name: "Staff", email: "staff@example.test", password: "Qa8chars", confirmPassword: "Qa8chars", isOwner: true });
  assert.equal(request.url, "/api/users");
  assert.equal(request.options.method, "POST");
  assert.deepEqual(JSON.parse(request.options.body), { name: "Staff", email: "staff@example.test", password: "Qa8chars", role: "Staff" });
});

test("editing sends a concurrency version and omits empty password and ownership fields", async (t) => {
  let body;
  t.mock.method(globalThis, "fetch", async (_url, options) => { body = JSON.parse(options.body); return new Response(JSON.stringify({ id: "staff" })); });
  await updateUser({ id: "staff", version: 3 }, { name: "Renamed", role: "Admin", isActive: false, password: "", isOwner: true });
  assert.deepEqual(body, { expectedVersion: 3, name: "Renamed", role: "Admin", isActive: false });
});

test("user management exposes permission and administrator-capacity errors", async (t) => {
  const fetch = t.mock.method(globalThis, "fetch", async () => new Response(JSON.stringify({ detail: "Only the Owner can manage accounts" }), { status: 403 }));
  await assert.rejects(createUser({}), /Only the Owner/);
  fetch.mock.mockImplementation(async () => new Response(JSON.stringify({ detail: "Maximum two Admin accounts allowed" }), { status: 409 }));
  await assert.rejects(updateUser({ id: "staff", version: 1 }, { role: "Admin" }), /Maximum two/);
});

test("malformed directory responses are rejected", async (t) => {
  t.mock.method(globalThis, "fetch", async () => new Response(JSON.stringify({ users: [] })));
  await assert.rejects(getUsers(), /invalid response/);
});
