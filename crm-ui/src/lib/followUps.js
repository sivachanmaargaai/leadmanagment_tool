import { displayDate, staffNames } from "./runtimeSettings.js";
export const FOLLOW_UP_KEY = "engen-crm-follow-ups";

export function istInput(value = new Date()) {
  const parts = Object.fromEntries(new Intl.DateTimeFormat("en-GB", {
    timeZone: "Asia/Kolkata", year: "numeric", month: "2-digit", day: "2-digit",
    hour: "2-digit", minute: "2-digit", hourCycle: "h23",
  }).formatToParts(new Date(value)).map(({ type, value: part }) => [type, part]));
  return `${parts.year}-${parts.month}-${parts.day}T${parts.hour}:${parts.minute}`;
}

export function fromIST(value) {
  const date = new Date(`${value}:00+05:30`);
  if (!value || !Number.isFinite(date.getTime())) throw new Error("Enter a valid date and time.");
  return date.toISOString();
}

export function formatFollowUpDate(value) {
  return displayDate(value, true);
}

export function isOverdue(item, now = Date.now()) {
  return item.status === "Pending" && new Date(item.dueAt).getTime() < now;
}

export function matchesFollowUpTab(item, tab, now = Date.now()) {
  if (tab === "All") return true;
  if (tab === "Completed") return item.status === "Completed";
  if (tab === "Overdue") return isOverdue(item, now);
  if (item.status !== "Pending") return false;
  const day = istInput(item.dueAt).slice(0, 10);
  const today = istInput(now).slice(0, 10);
  return tab === "Today" ? day === today : tab === "Upcoming" && day > today;
}

export function followUpAlert(item, now = Date.now()) {
  return item.status === "Pending" &&
    new Date(item.dueAt).getTime() - Number(item.reminderMinutes || 0) * 60000 <= now;
}

export function resolveFollowUp(item, leads) {
  const lead = leads.find((entry) => entry.id === item.leadId);
  return { ...item, customer: lead?.customer || item.customer, division: lead?.division || item.division,
    referredBy: lead?.referredBy ?? item.referredBy, leadSource: lead?.leadSource || item.leadSource };
}

export function readStaff() {
  const names = staffNames();
  return names.length ? names : ["Admin"];
}
