import { getCompleteList, getListPage, requireVersion } from "./paginationApi.js";
import { apiRequest } from "./apiClient.js";

export function followUpPayload(record) {
  const fields = ["leadId", "purpose", "type", "dueAt", "assignedTo", "priority", "reminderMinutes", "notes"];
  return Object.fromEntries(fields.filter((field) => record[field] !== undefined).map((field) => [field, record[field]]));
}

export const getFollowUps = (filters) => getCompleteList("/api/follow-ups", filters);
export const getFollowUpsPage = (filters) => getListPage("/api/follow-ups", filters);
export const getFollowUpById = (id) => apiRequest(`/api/follow-ups/${encodeURIComponent(id)}`);
export const getUpcomingFollowUps = () => getCompleteList("/api/follow-ups/upcoming");
export const getOverdueFollowUps = () => getCompleteList("/api/follow-ups/overdue");
export const createFollowUp = (record) => apiRequest("/api/follow-ups", { method: "POST", body: JSON.stringify(followUpPayload(record)) });
export function updateFollowUp(record, next) {
  const { leadId, ...payload } = followUpPayload(record);
  // The linked lead stays fixed; concurrency and history are server controlled.
  void leadId;
  payload.expectedVersion = requireVersion(record.version);
  payload.status = record.status;
  if (record.status === "Completed") {
    payload.outcome = record.outcome;
    payload.completionNotes = record.completionNotes;
    if (next) payload.nextDueAt = next.dueAt;
  } else if (record.rescheduleReason) {
    payload.rescheduleReason = record.rescheduleReason;
  }
  return apiRequest(`/api/follow-ups/${encodeURIComponent(record.id)}`, { method: "PUT", body: JSON.stringify(payload) });
}
export const deleteFollowUp = (id, version) => apiRequest(`/api/follow-ups/${encodeURIComponent(id)}?expectedVersion=${requireVersion(version)}`, { method: "DELETE" });
