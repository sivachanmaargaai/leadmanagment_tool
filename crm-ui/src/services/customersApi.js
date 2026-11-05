import { getCompleteList, getListPage, requireVersion } from "./paginationApi.js";
import { apiRequest } from "./apiClient.js";

// Send writable fields only; IDs, timestamps and computed directory fields stay out.
export function customerPayload(customer) {
  const fields = ["name", "type", "divisions", "contacts", "address", "city", "state", "postcode", "gst", "assignedTo", "notes", "leadSource", "referredBy", "referenceNotes", "aliases", "history"];
  return Object.fromEntries(fields.filter((field) => customer[field] !== undefined).map((field) => [field, customer[field]]));
}

export const getCustomers = (filters) => getCompleteList("/api/customers", filters);
export const getCustomersPage = (filters) => getListPage("/api/customers", filters);
export const getCustomerById = (id) => apiRequest(`/api/customers/${encodeURIComponent(id)}`);
export const createCustomer = (customer) => apiRequest("/api/customers", { method: "POST", body: JSON.stringify(customerPayload(customer)) });
export const updateCustomer = (id, customer) => apiRequest(`/api/customers/${encodeURIComponent(id)}`, { method: "PUT", body: JSON.stringify({ ...customerPayload(customer), expectedVersion: requireVersion(customer.version) }) });
export const deleteCustomer = (id, version) => apiRequest(`/api/customers/${encodeURIComponent(id)}?expectedVersion=${requireVersion(version)}`, { method: "DELETE" });
