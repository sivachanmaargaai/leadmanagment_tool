import assert from "node:assert/strict";
import test from "node:test";
import { acceptAuthentication, apiRequest, clearAuthentication, refreshAuthentication } from "./apiClient.js";
import { login, logout, restoreSession } from "./authApi.js";

const user = { id: "user-1", email: "owner@example.test", name: "Owner", role: "Admin", isActive: true };
const tokens = (accessToken = "test-access") => ({ accessToken, tokenType: "Bearer", expiresIn: 900, user });
const json = (value, status = 200) => new Response(JSON.stringify(value), { status, headers: { "Content-Type": "application/json" } });

test.beforeEach(() => clearAuthentication());

test("login sends JSON credentials and adds memory-only bearer authentication to API requests", async (t) => {
  const calls = [];
  t.mock.method(globalThis, "fetch", async (url, options) => {
    calls.push({ url, options });
    return json(url.endsWith("/login") ? tokens() : []);
  });
  assert.deepEqual(await login("owner@example.test", "  spaces matter  "), user);
  await apiRequest("/api/leads");
  assert.deepEqual(JSON.parse(calls[0].options.body), { email: "owner@example.test", password: "  spaces matter  " });
  assert.equal(calls[0].options.headers.Authorization, undefined);
  assert.equal(calls[1].options.headers.Authorization, "Bearer test-access");
  assert.equal(calls[0].options.headers["X-CRM-Request"], "1");
  assert.equal(calls[0].options.credentials, "include");
});

test("session restoration deduplicates simultaneous cookie rotation requests", async (t) => {
  let refreshes = 0;
  t.mock.method(globalThis, "fetch", async (url) => {
    if (url.endsWith("/refresh")) { ++refreshes; return json(tokens()); }
    return json(user);
  });
  const restored = await Promise.all([restoreSession(), restoreSession()]);
  assert.equal(refreshes, 1);
  assert.deepEqual(restored, [user, user]);
});

test("concurrent expired API calls share one refresh and retry with the new token", async (t) => {
  acceptAuthentication(tokens("old-token"));
  let refreshes = 0;
  const requests = [];
  t.mock.method(globalThis, "fetch", async (url, options) => {
    if (url.endsWith("/refresh")) { ++refreshes; return json(tokens("new-token")); }
    requests.push(options.headers.Authorization);
    return options.headers.Authorization === "Bearer old-token" ? json({ detail: "Expired" }, 401) : json([]);
  });
  await Promise.all([apiRequest("/api/leads"), apiRequest("/api/customers")]);
  assert.equal(refreshes, 1);
  assert.equal(requests.filter((value) => value === "Bearer new-token").length, 2);
});

test("failed refresh clears authentication and does not loop API retries", async (t) => {
  acceptAuthentication(tokens());
  const urls = [];
  t.mock.method(globalThis, "fetch", async (url) => { urls.push(url); return json({ detail: "Sign in to continue" }, 401); });
  await assert.rejects(apiRequest("/api/leads"), (error) => error.status === 401);
  assert.equal(urls.length, 2);
  const calls = [];
  t.mock.restoreAll();
  t.mock.method(globalThis, "fetch", async (_url, options) => { calls.push(options); return json([]); });
  await apiRequest("/api/leads");
  assert.equal(calls[0].headers.Authorization, undefined);
});

test("logout is confirmed by the server before forgetting the current session", async (t) => {
  acceptAuthentication(tokens());
  const calls = [];
  const fetch = t.mock.method(globalThis, "fetch", async (url, options) => { calls.push({ url, options }); return json({ detail: "Try again" }, 503); });
  await assert.rejects(logout(), /Try again/);
  fetch.mock.mockImplementation(async (url, options) => { calls.push({ url, options }); return url.endsWith("/logout") ? new Response(null, { status: 204 }) : json([]); });
  await apiRequest("/api/leads");
  assert.equal(calls.at(-1).options.headers.Authorization, "Bearer test-access");
  await logout();
  await apiRequest("/api/leads");
  assert.equal(calls.at(-1).options.headers.Authorization, undefined);
});

test("an in-flight refresh cannot restore a session cleared by logout", async (t) => {
  let complete;
  let started;
  const requestStarted = new Promise((resolve) => { started = resolve; });
  t.mock.method(globalThis, "fetch", async () => { started(); return new Promise((resolve) => { complete = resolve; }); });
  const pending = refreshAuthentication();
  await requestStarted;
  clearAuthentication();
  complete(json(tokens("stale-token")));
  await assert.rejects(pending, /Session changed/);
});

test("login errors never refresh automatically and aborted requests remain aborted", async (t) => {
  const calls = [];
  const fetch = t.mock.method(globalThis, "fetch", async (url) => { calls.push(url); return json({ detail: "Sign in to continue" }, 401); });
  await assert.rejects(login(user.email, "wrong password"), (error) => error.status === 401);
  assert.equal(calls.length, 1);
  fetch.mock.mockImplementation(async () => { throw new DOMException("Aborted", "AbortError"); });
  await assert.rejects(apiRequest("/api/leads"), (error) => error.name === "AbortError");
});
