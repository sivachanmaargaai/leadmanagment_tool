export function parseResetLink(hash) {
  if (!hash?.startsWith("#reset-password")) return null;
  const token = hash.length <= 512 ? new URLSearchParams(hash.split("?")[1] || "").get("token") || "" : "";
  return /^[A-Za-z0-9_-]{43,128}$/.test(token) ? { token, valid: true } : { token: "", valid: false };
}

export function consumeResetLink() {
  if (typeof window === "undefined") return null;
  const link = parseResetLink(window.location.hash);
  if (link) window.history.replaceState(window.history.state, "", window.location.pathname + window.location.search);
  return link;
}
