import assert from "node:assert/strict";
import test from "node:test";
import { customerFormPayload } from "../lib/customerForm.js";

const input = () => ({ form: { name: "Embedded Customer", type: "Company", address: " Chennai ", city: "Chennai", state: "TN", postcode: "600001", gst: "GST", notes: "Retain notes" }, contacts: [{ name: " Chan ", designation: "Manager", phone: "1234567890", email: "chan@example.test" }], selectedDivisions: ["MMC"], referral: new FormData(), userName: "Owner" });
test("customer form preserves profile fields, contacts, aliases and history on rename", () => {
  const result = customerFormPayload({ ...input(), customer: { id: "customer-id", name: "Old Name", aliases: ["Older"], assignedTo: "Staff", history: [{ id: "previous", message: "Earlier entry" }] } });
  assert.equal(result.id, "customer-id");
  assert.equal(result.contacts[0].name, "Chan");
  assert.equal(result.address, "Chennai");
  assert.equal(result.notes, "Retain notes");
  assert.deepEqual(result.aliases, ["Older", "Old Name"]);
  assert.equal(result.history[0].id, "previous");
  assert.match(result.history[1].message, /renamed/);
});
test("customer form retains referral details and requires primary contact and divisions", () => {
  const value = input();
  for (const [key, item] of Object.entries({ leadSource: "Known Network", referredById: "ref", referredByName: "Introducer", referredByCompany: "Network", referredByPhone: "123", referredByEmail: "ref@example.test", referenceNotes: "Introduction" })) value.referral.set(key, item);
  const result = customerFormPayload(value);
  assert.equal(result.referredBy.email, "ref@example.test");
  assert.equal(result.referenceNotes, "Introduction");
  assert.throws(() => customerFormPayload({ ...value, contacts: [] }), /primary phone/);
  assert.throws(() => customerFormPayload({ ...value, selectedDivisions: [] }), /division/);
  value.referral.delete("referredById");
  assert.throws(() => customerFormPayload(value), /reference contact/);
});
