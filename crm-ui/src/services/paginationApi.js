import { apiRequest } from "./apiClient.js";

export function listQuery(filters = {}) {
  const query = new URLSearchParams({ paged: "true", page: String(filters.page || 1), pageSize: String(filters.pageSize || 100) });
  for (const [key, value] of Object.entries(filters)) {
    const allFilter = ["division", "status", "type", "assignedTo"].includes(key) && String(value).startsWith("All ");
    if (!["page", "pageSize", "paged", "signal"].includes(key) && value !== undefined && value !== null && value !== "" && !allFilter) query.set(key, String(value));
  }
  return query.toString();
}

export async function getListPage(path, filters = {}) {
  const result = await apiRequest(`${path}?${listQuery(filters)}`, { signal: filters.signal });
  if (!Array.isArray(result?.items) || !Number.isSafeInteger(result.total) || result.total < 0 || !Number.isSafeInteger(result.page) || result.page < 1 || !Number.isSafeInteger(result.pageSize) || result.pageSize < 1 || result.pageSize > 100 || !Number.isSafeInteger(result.pages) || result.pages < 1 || typeof result.hasMore !== "boolean") throw new Error("The API returned an invalid list page. Reload and try again.");
  return result;
}

// Explicit full-data consumers (dashboard, related-record views/export) traverse
// bounded pages rather than silently treating the first page as the whole register.
export async function getCompleteList(path, filters = {}) {
  const records = new Map();
  let page = 1;
  let total;
  while (true) {
    const result = await getListPage(path, { ...filters, page, pageSize: 100 });
    if (result.page !== page || (total !== undefined && total !== result.total)) throw new Error("The list changed while loading. Reload to get a consistent view.");
    total = result.total;
    for (const item of result.items) {
      if (!item?.id || records.has(item.id)) throw new Error("The list changed while loading. Reload to get a consistent view.");
      records.set(item.id, item);
    }
    if (!result.hasMore) break;
    if (!result.items.length || page >= 10000) throw new Error("The list could not be loaded completely. Narrow the filters and retry.");
    ++page;
  }
  if (records.size !== total) throw new Error("The list changed while loading. Reload to get a consistent view.");
  return [...records.values()];
}

export function requireVersion(version) {
  if (!Number.isSafeInteger(version) || version < 1) throw new Error("Reload this record before editing or deleting it.");
  return version;
}
