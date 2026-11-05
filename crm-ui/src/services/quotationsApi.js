import { getCompleteList, getListPage } from "./paginationApi.js";
import { apiRequest } from "./apiClient.js";

export function quotationPayload(quote) {
  const fields = ["number", "customer", "customerId", "contact", "address", "division", "date", "validUntil", "status", "currency", "tax", "terms", "billing"];
  const payload = Object.fromEntries(fields.filter((key) => quote[key] !== undefined).map((key) => [key, quote[key]]));
  payload.amount = quote.amount === "" || quote.amount == null ? 0 : Number(quote.amount);
  payload.items = (quote.items || []).map(({ description, quantity, rate, billing }) => ({ description, quantity, rate, billing }));
  return payload;
}

export const getQuotations = (filters) => getCompleteList("/api/quotations", filters);
export const getQuotationsPage = (filters) => getListPage("/api/quotations", filters);

export function createQuotation(quote, file) {
  const payload = quotationPayload(quote);
  if (!file) return apiRequest("/api/quotations", { method: "POST", body: JSON.stringify(payload) });
  const body = new FormData();
  body.append("metadata", JSON.stringify(payload));
  body.append("file", file);
  return apiRequest("/api/quotations/upload", { method: "POST", body });
}

export function updateQuotation(quote, changes) {
  const payload = changes.document ? { document: quotationPayload(changes.document) } : { status: changes.status };
  return apiRequest(`/api/quotations/${encodeURIComponent(quote.id)}`, { method: "PUT", body: JSON.stringify({ ...payload, expectedVersion: quote.version }) });
}

export function uploadQuotationRevision(quote, file, document) {
  const body = new FormData();
  body.append("file", file);
  body.append("expectedVersion", String(quote.version));
  if (document) body.append("metadata", JSON.stringify(quotationPayload(document)));
  return apiRequest(`/api/quotations/${encodeURIComponent(quote.id)}/revisions`, { method: "POST", body });
}

export function deleteQuotation(quote) {
  return apiRequest(`/api/quotations/${encodeURIComponent(quote.id)}?expectedVersion=${quote.version}`, { method: "DELETE" });
}

export function getQuotationPdf(version) {
  // Accept only the API's quotation revision routes, never arbitrary external URLs.
  if (!/^\/api\/quotations\/[a-zA-Z0-9-]+\/versions\/[a-zA-Z0-9-]+\/pdf$/.test(version.pdfPath || "")) {
    throw new Error("PDF revision is unavailable. Reload quotations.");
  }
  return apiRequest(version.pdfPath, { responseType: "blob" });
}

export const getQuotationById = (id) => apiRequest(`/api/quotations/${encodeURIComponent(id)}`);
