import test from "node:test";
import assert from "node:assert/strict";
import { istInput, fromIST, matchesFollowUpTab, isOverdue, followUpAlert, resolveFollowUp } from "./followUps.js";

test("IST input round-trips across UTC midnight", () => {
  assert.equal(istInput("2026-11-02T20:00:00Z"), "2026-11-03T01:30");
  assert.equal(fromIST("2026-11-03T01:30"), "2026-11-02T20:00:00.000Z");
});

test("today uses IST dates and excludes completed tasks", () => {
  const now = Date.parse("2026-11-02T20:00:00Z");
  const item = { status: "Pending", dueAt: "2026-11-03T10:00:00Z" };
  assert.equal(matchesFollowUpTab(item, "Today", now), true);
  assert.equal(matchesFollowUpTab({ ...item, status: "Completed" }, "Today", now), false);
  assert.equal(matchesFollowUpTab({ ...item, dueAt: "2026-11-03T20:00:00Z" }, "Upcoming", now), true);
});

test("overdue and reminder boundaries respect task status", () => {
  const due = Date.parse("2026-11-03T10:00:00Z");
  const item = { status: "Pending", dueAt: new Date(due).toISOString(), reminderMinutes: 30 };
  assert.equal(isOverdue(item, due), false);
  assert.equal(isOverdue(item, due + 1), true);
  assert.equal(followUpAlert(item, due - 1800001), false);
  assert.equal(followUpAlert(item, due - 1800000), true);
  assert.equal(followUpAlert({ ...item, status: "Completed" }, due + 1), false);
});

test("reference details come from the linked lead and retain a fallback snapshot", () => {
  const item = { leadId: "lead-1", customer: "Snapshot", referredBy: { name: "Old" } };
  assert.equal(resolveFollowUp(item, [{ id: "lead-1", customer: "Customer", referredBy: { name: "Ramesh" } }]).referredBy.name, "Ramesh");
  assert.equal(resolveFollowUp(item, []).customer, "Snapshot");
});
