import { apiRequest } from "./apiClient.js";

function valid(data) {
  if (!Number.isSafeInteger(data?.version) || data.version < 1 || typeof data.roles?.Staff?.quotations !== "boolean" || data.roles?.Admin?.quotations !== true || data.roles?.Admin?.readOnly !== true) throw new Error("The permissions API returned an invalid response.");
  return data;
}

export async function getRolePermissions(signal) {
  return valid(await apiRequest("/api/permissions", { signal }));
}

export async function saveStaffPermissions(quotations, version) {
  return valid(await apiRequest("/api/permissions/staff", { method: "PUT", body: JSON.stringify({ quotations, expectedVersion: version }) }));
}
