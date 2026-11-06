import { apiRequest } from "./apiClient.js";

const statusFields = { leads: "leadStatus", sales: "quoteStatus", "follow-ups": "followUpStatus" };

export function reportQuery(filters = {}, kind = "summary") {
  const query = new URLSearchParams();
  for (const key of ["startDate", "endDate", "division"]) {
    if (filters[key]) query.set(key, filters[key]);
  }
  query.set("includeTestData", String(Boolean(filters.includeTestData)));
  if (filters[statusFields[kind]]) query.set("status", filters[statusFields[kind]]);
  return query.toString();
}

export async function getReport(kind, filters = {}, signal) {
  if (!["summary", "leads", "sales", "follow-ups"].includes(kind)) throw new Error("Unknown report type.");
  const data = await apiRequest(`/api/reports/${kind}?${reportQuery(filters, kind)}`, { signal });
  if (!data || !data.filters || (kind === "summary" ? !data.totals : !Array.isArray(data.rows))) {
    throw new Error("The reports API returned an invalid response.");
  }
  return data;
}

export async function getReports(filters, signal, canAccessQuotations = true) {
  const kinds = ["summary", "leads", ...(canAccessQuotations ? ["sales"] : []), "follow-ups"];
  const results = await Promise.all(kinds.map((kind) => getReport(kind, filters, signal)));
  return Object.fromEntries(kinds.map((kind, index) => [kind, results[index]]));
}
