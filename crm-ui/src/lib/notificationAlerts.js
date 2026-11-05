import { followUpAlert, formatFollowUpDate, isOverdue, istInput } from "./followUps.js";

export function notificationAlerts({ leads, followUps, quotes, notifications, division, now }) {
  const visible = (item) => division === "All divisions" || item.division === division;
  const leadAlerts = notifications.leadPriority ? leads.filter((item) => visible(item) && item.priority === "High" && !["Won", "Lost"].includes(item.status)).map((item) => ({ ...item, alertLabel: "High-priority lead" })) : [];
  const taskAlerts = followUps.filter((item) => visible(item) && (isOverdue(item, now) ? notifications.overdue : notifications.followUp && followUpAlert(item, now))).map((item) => ({ id: `followup-${item.id}`, customer: item.customer, division: item.division, description: `${item.purpose} · ${formatFollowUpDate(item.dueAt)} IST`, alertLabel: isOverdue(item, now) ? "Overdue follow-up" : "Follow-up reminder" }));
  const today = istInput(now).slice(0, 10);
  const soon = new Date(Date.parse(`${today}T00:00:00Z`) + 2 * 86400000).toISOString().slice(0, 10);
  const quoteAlerts = notifications.quotationExpiry ? quotes.filter((item) => visible(item) && ["Sent", "Expired"].includes(item.status) && item.validUntil <= soon).map((item) => ({ id: `quote-${item.id}`, customer: item.customer, division: item.division, description: `${item.number} · Valid until ${item.validUntil}`, alertLabel: item.validUntil < today || item.status === "Expired" ? "Quotation expired" : "Quotation expiring soon" })) : [];
  return [...taskAlerts, ...leadAlerts, ...quoteAlerts];
}
