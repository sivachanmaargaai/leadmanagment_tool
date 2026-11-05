import { apiRequest } from "./apiClient.js";

export async function getUsers() {
  const data = await apiRequest("/api/users");
  if (!Array.isArray(data?.users) || typeof data.canManageUsers !== "boolean") throw new Error("The users API returned an invalid response.");
  return data;
}

export function createUser(form) {
  return apiRequest("/api/users", { method: "POST", body: JSON.stringify({ name: form.name, email: form.email, role: form.role || "Staff", password: form.password }) });
}

export function updateUser(account, form) {
  const payload = { expectedVersion: account.version };
  for (const key of ["name", "email", "role", "isActive"]) if (form[key] !== undefined) payload[key] = form[key];
  if (form.password) payload.password = form.password;
  return apiRequest(`/api/users/${encodeURIComponent(account.id)}`, { method: "PUT", body: JSON.stringify(payload) });
}
