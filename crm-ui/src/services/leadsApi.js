import { getCompleteList, getListPage, requireVersion } from "./paginationApi.js";
import { apiRequest } from "./apiClient.js";

// GET all leads
export const getLeads = (filters) => getCompleteList("/api/leads", filters);
export const getLeadsPage = (filters) => getListPage("/api/leads", filters);

// GET single lead
export function getLeadById(id) {
    return apiRequest(`/api/leads/${encodeURIComponent(id)}`);
}

// CREATE lead

export function createLead(lead) {
    const payload = { ...lead };

    delete payload.id;
    delete payload.createdAt;
    delete payload.updatedAt;
    delete payload.assigneeUserId;
    delete payload.version;
    delete payload.expectedVersion;

    return apiRequest("/api/leads", {
        method: "POST",
        body: JSON.stringify(payload),
    });
}


// UPDATE lead
export function updateLead(id, updates) {
    return apiRequest(
        `/api/leads/${encodeURIComponent(id)}`,
        {
            method: "PUT",
            body: JSON.stringify({ ...updates, expectedVersion: requireVersion(updates.expectedVersion) }),
        }
    );
}

// DELETE lead
export function deleteLead(id, version) {
    return apiRequest(
        `/api/leads/${encodeURIComponent(id)}?expectedVersion=${requireVersion(version)}`,
        {
            method: "DELETE",
        }
    );
}
