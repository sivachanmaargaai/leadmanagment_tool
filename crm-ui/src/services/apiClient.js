// Development always uses Vite's local /api proxy, even if a stale cloud URL
// exists in a developer's environment. Production can use its own build setting.
const API_BASE_URL = import.meta.env?.DEV ? "" : (import.meta.env?.VITE_API_BASE_URL || "").replace(/\/$/, "");
let accessToken = null;
let refreshPromise = null;
let authGeneration = 0;

export class ApiError extends Error {
  constructor(message, status = 0, retryAfter = null, requestId = null) { super(message); this.name = "ApiError"; this.status = status; this.retryAfter = retryAfter; this.requestId = requestId; }
}

export function acceptAuthentication(data) {
  if (!data?.accessToken || data.tokenType !== "Bearer" || !data.user?.id) throw new ApiError("The authentication API returned an invalid response.");
  ++authGeneration;
  accessToken = data.accessToken;
  return data.user;
}

export function clearAuthentication() {
  ++authGeneration;
  accessToken = null;
  if (typeof window !== "undefined") window.dispatchEvent(new Event("crm:session-expired"));
}

export function refreshAuthentication() {
  if (refreshPromise) return refreshPromise;
  const generation = authGeneration;
  const refresh = async () => {
    try {
      if (generation !== authGeneration) throw new ApiError("Session changed. Please sign in again.", 401);
      const data = await apiRequest("/api/auth/refresh", { method: "POST", auth: false, skipAuthRetry: true });
      if (generation !== authGeneration) throw new ApiError("Session changed. Please sign in again.", 401);
      if (!data?.accessToken || data.tokenType !== "Bearer" || !data.user?.id) throw new ApiError("The authentication API returned an invalid response.");
      accessToken = data.accessToken;
      return data;
    } catch (error) {
      if (generation === authGeneration && error.status === 401) clearAuthentication();
      throw error;
    }
  };
  // Serialize cookie rotation across tabs when Web Locks is available.
  const work = globalThis.navigator?.locks?.request
    ? navigator.locks.request("engen-crm-session-refresh", refresh) : refresh();
  refreshPromise = work.finally(() => { refreshPromise = null; });
  return refreshPromise;
}

export async function apiRequest(path, options = {}) {
  const { responseType, auth = true, skipAuthRetry = false, ...requestOptions } = options;
  const tokenAtSend = auth ? accessToken : null;
  let response;
  try {
    response = await fetch(`${API_BASE_URL}${path}`, {
      ...requestOptions,
      credentials: "include",
      headers: { "X-CRM-Request": "1", ...(options.body && !(options.body instanceof FormData) ? { "Content-Type": "application/json" } : {}), ...(tokenAtSend ? { Authorization: `Bearer ${tokenAtSend}` } : {}), ...options.headers },
    });
  } catch (error) {
    if (error.name === "AbortError") throw error;
    throw new ApiError("Cannot connect to backend. Check that the API server is running.");
  }
  if (response.status === 401 && auth && !skipAuthRetry) {
    if (!accessToken || accessToken === tokenAtSend) await refreshAuthentication();
    return apiRequest(path, { ...options, skipAuthRetry: true });
  }
  if (response.status === 204) return null;
  if (response.ok && responseType === "blob") {
    if (!response.headers.get("content-type")?.startsWith("application/pdf")) throw new Error("The API did not return a PDF.");
    return response.blob();
  }
  const data = await response.json().catch(() => null);
  if (!response.ok) {
    const detail = data?.detail;
    let message = typeof detail === "string" ? detail : Array.isArray(detail)
      ? detail.map((item) => `${item.loc?.slice(1).join(".") || "Request"}: ${item.msg}`).join("; ")
      : `Request failed (${response.status})`;
    if (response.status === 401 && auth) clearAuthentication();
    const rawRetry = response.headers?.get?.("retry-after");
    const retryAfter = rawRetry && /^\d+$/.test(rawRetry) ? Math.min(86400, Number(rawRetry)) : null;
    if (response.status === 429 && retryAfter) message += ` Try again in ${retryAfter} seconds.`;
    const reference = response.headers?.get?.("x-request-id");
    const requestId = reference && /^[a-f0-9-]{36}$/i.test(reference) ? reference : null;
    if (response.status >= 500 && requestId) message += ` Reference: ${requestId}.`;
    throw new ApiError(message, response.status, retryAfter, requestId);
  }
  if (data === null) throw new Error("The API returned an invalid response. Please retry.");
  return data;
}
