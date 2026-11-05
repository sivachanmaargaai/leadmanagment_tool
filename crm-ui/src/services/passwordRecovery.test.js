import assert from "node:assert/strict";
import test from "node:test";
import { forgotPassword, resetPassword } from "./authApi.js";
import { parseResetLink, consumeResetLink } from "../lib/resetLink.js";

const token = "x".repeat(43);
const json = (value, status = 200) => new Response(JSON.stringify(value), { status, headers: { "Content-Type": "application/json" } });

test("reset fragment parsing rejects missing or malformed secrets", () => {
  assert.equal(parseResetLink("#dashboard"), null);
  assert.deepEqual(parseResetLink(`#reset-password?token=${token}`), { token, valid: true });
  for (const hash of ["#reset-password", "#reset-password?token=short", "#reset-password?token=" + "x".repeat(600)]) {
    assert.equal(parseResetLink(hash).valid, false);
  }
});

test("reset link is removed from browser history immediately", (t) => {
  const calls = [];
  globalThis.window = { location: { hash: `#reset-password?token=${token}`, pathname: "/", search: "" }, history: { state: null, replaceState: (...args) => calls.push(args) } };
  t.after(() => { delete globalThis.window; });
  assert.equal(consumeResetLink().token, token);
  assert.deepEqual(calls, [[null, "", "/"]]);
});

test("recovery calls use public JSON endpoints without bearer credentials", async (t) => {
  const calls = [];
  t.mock.method(globalThis, "fetch", async (url, options) => { calls.push({ url, options }); return url.endsWith("forgot-password") ? json({ message: "Generic reply", expiresInMinutes: 15 }, 202) : new Response(null, { status: 204 }); });
  await forgotPassword("owner@example.test");
  await resetPassword(token, "New8char");
  assert.deepEqual(JSON.parse(calls[1].options.body), { token, newPassword: "New8char" });
  assert.ok(calls.every(({ options }) => options.headers.Authorization === undefined && options.headers["X-CRM-Request"] === "1" && options.credentials === "include"));
});

test("recovery errors do not trigger login refresh or automatic retries", async (t) => {
  let calls = 0;
  t.mock.method(globalThis, "fetch", async () => { calls++; return json({ detail: "Expired link" }, 400); });
  await assert.rejects(resetPassword(token, "New8char"), (error) => error.status === 400);
  assert.equal(calls, 1);
});

test("malformed recovery response is rejected", async (t) => {
  t.mock.method(globalThis, "fetch", async () => json({ message: "Missing expiry" }));
  await assert.rejects(forgotPassword("owner@example.test"), /invalid response/);
});
