import { acceptAuthentication, apiRequest, clearAuthentication, refreshAuthentication } from "./apiClient.js";

export async function login(email, password) {
  const data = await apiRequest("/api/auth/login", { method: "POST", auth: false, skipAuthRetry: true, body: JSON.stringify({ email, password }) });
  return acceptAuthentication(data);
}

export async function restoreSession() {
  await refreshAuthentication();
  return apiRequest("/api/auth/me");
}

export async function logout(allDevices = false) {
  await apiRequest(allDevices ? "/api/auth/logout-all" : "/api/auth/logout", { method: "POST", skipAuthRetry: !allDevices });
  clearAuthentication();
}

export async function forgotPassword(email) {
  const result = await apiRequest("/api/auth/forgot-password", { method: "POST", auth: false, skipAuthRetry: true, body: JSON.stringify({ email }) });
  if (typeof result?.message !== "string" || !Number.isFinite(result.expiresInMinutes)
    || !/^[A-Za-z0-9_-]{43,128}$/.test(result.challengeId ?? "")
    || !Number.isFinite(result.resendAfterSeconds)) throw new Error("The recovery API returned an invalid response.");
  return result;
}

export async function verifyRecoveryOtp(challengeId, code) {
  const result = await apiRequest("/api/auth/verify-reset-otp", { method: "POST", auth: false, skipAuthRetry: true, body: JSON.stringify({ challengeId, code }) });
  if (!/^[A-Za-z0-9_-]{43,128}$/.test(result?.resetToken ?? "")) throw new Error("The recovery API returned an invalid response.");
  return result;
}

export async function resetPassword(token, newPassword) {
  await apiRequest("/api/auth/reset-password", { method: "POST", auth: false, skipAuthRetry: true, body: JSON.stringify({ token, newPassword }) });
  clearAuthentication();
}
