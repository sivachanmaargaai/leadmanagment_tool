import { apiRequest, clearAuthentication } from "./apiClient.js";

function valid(data) {
  if (!data?.profile || !data.company || !data.divisions || !data.leads || (!data.quotation && data.canAccessQuotations !== false) || !data.notifications || !data.workspace || !data.versions) throw new Error("The settings API returned an invalid response.");
  return data;
}

export async function getSettings() { return valid(await apiRequest("/api/settings")); }

export function settingsPayload(settings) {
  const payload = { expectedPersonalVersion: settings.versions.personal, expectedProfileVersion: settings.versions.profile,
    profile: { name: settings.profile.name, phone: settings.profile.phone, designation: settings.profile.designation },
    notifications: { ...settings.notifications, reminderBefore: Number(settings.notifications.reminderBefore) },
    workspace: { ...settings.workspace, rowsPerPage: Number(settings.workspace.rowsPerPage) } };
  if (settings.canManageShared) Object.assign(payload, {
    expectedSharedVersion: settings.versions.shared, company: settings.company, divisions: settings.divisions,
    leads: { ...settings.leads, followUpDays: Number(settings.leads.followUpDays), sources: typeof settings.leads.sources === "string" ? settings.leads.sources.split(",").map((value) => value.trim()).filter(Boolean) : settings.leads.sources },
    quotation: { ...settings.quotation, nextNumber: Number(settings.quotation.nextNumber), validity: Number(settings.quotation.validity), tax: Number(settings.quotation.tax || 0) },
  });
  return payload;
}

export async function saveSettings(settings) {
  return valid(await apiRequest("/api/settings", { method: "PUT", body: JSON.stringify(settingsPayload(settings)) }));
}

export async function changePassword(currentPassword, newPassword) {
  await apiRequest("/api/auth/change-password", { method: "POST", body: JSON.stringify({ currentPassword, newPassword }) });
  clearAuthentication();
}
