import { apiRequest } from "./apiClient.js";

export async function getOperationsStatus(signal) {
  const data = await apiRequest("/api/ops/status", { signal });
  if (!["ok", "warning", "critical"].includes(data?.status) || !Array.isArray(data?.issues) || typeof data?.database?.reachable !== "boolean" || typeof data?.database?.schemaCurrent !== "boolean" || typeof data?.backup?.status !== "string" || !Number.isFinite(data?.metrics?.requests)) throw new Error("The monitoring API returned an invalid status.");
  return data;
}
