import assert from "node:assert/strict";
import test from "node:test";
import { readReferenceContacts, saveReferenceContacts } from "../lib/referenceContacts.js";

test("reference pickers separate accounts and preserve unimported legacy registry", () => {
  const old = JSON.stringify([{ id: "legacy", name: "Old contact" }]);
  const map = new Map([["engen-reference-contacts", old]]);
  const storage = { getItem: (key) => map.get(key) ?? null, setItem: (key, value) => map.set(key, value) };
  assert.deepEqual(readReferenceContacts("staff-a", storage), []);
  saveReferenceContacts("staff-a", [{ id: "ref", name: "A's contact" }], storage);
  assert.equal(readReferenceContacts("staff-a", storage).length, 1);
  assert.deepEqual(readReferenceContacts("staff-b", storage), []);
  assert.equal(map.get("engen-reference-contacts"), old);
  assert.throws(() => saveReferenceContacts("", [], storage), /Sign in/);
});
