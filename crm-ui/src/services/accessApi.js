import { requireVersion } from "./paginationApi.js";
import { apiRequest } from "./apiClient.js";

export async function getAssignments(module, offset = 0, signal) {
  const result = await apiRequest(`/api/access/assignments?module=${encodeURIComponent(module)}&offset=${offset}&limit=25`, { signal });
  if (!Array.isArray(result?.records) || !Array.isArray(result?.users) || typeof result.hasMore !== "boolean") throw new Error("The assignment API returned an invalid response.");
  return result;
}

export function assignRecord(module, record, assigneeUserId) {
  return apiRequest(`/api/access/assignments/${encodeURIComponent(module)}/${encodeURIComponent(record.id)}`, {
    method: "PUT", body: JSON.stringify({ assigneeUserId: assigneeUserId || null, expectedAssigneeUserId: record.assigneeUserId, expectedVersion: requireVersion(record.version) }),
  });
}
