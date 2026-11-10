import { divisions } from "../data/crm.js";

const divisionPrefixes = { MMC: "MMC", nemilink: "NEM", "ClearCode Labs": "CCL", ENGEN: "ENG", Visotonics: "VIS", Overview: "OVW" };

export function defaultSettings() {
  return {
    profile: { name: "", email: "", phone: "", designation: "" },
    company: { name: "ENGEN", email: "", phone: "", address: "", gst: "", website: "" },
    divisions: Object.fromEntries(divisions.map((name) => [name, { name, address: "", gst: "", prefix: divisionPrefixes[name] }])),
    leads: { defaultPriority: "Medium", defaultStatus: "New", sources: ["Website", "Referral", "Phone", "Email", "Exhibition"], followUpDays: 2, requireContact: false, requireDescription: true },
    quotation: { prefix: "ENG", nextNumber: 1001, currency: "INR", validity: 15, tax: 0, paymentTerms: "", warranty: "", notes: "", showLogo: true, showSignature: true, approvalRequired: false },
    notifications: { leadPriority: true, followUp: true, overdue: true, quotationExpiry: true, reminderBefore: 30, sound: false },
    workspace: { sidebar: "Hover to expand", defaultDivision: "All divisions", rowsPerPage: 10, dateFormat: "DD MMM YYYY" },
    versions: { shared: 1, personal: 0, profile: 1 }, canManageShared: false,
  };
}

let current = defaultSettings();
let staff = [];
export function setRuntimeSettings(settings, names) { current = settings; if (names) staff = names; }
export function runtimeSettings() { return current; }
export function staffNames() { return [...new Set([current.profile.name, ...staff].filter(Boolean))]; }

export function displayDate(value, withTime = false) {
  const date = new Date(value);
  if (!Number.isFinite(date.getTime())) return "—";
  const parts = Object.fromEntries(new Intl.DateTimeFormat("en-GB", { timeZone: "Asia/Kolkata", day: "2-digit", month: "2-digit", year: "numeric" }).formatToParts(date).map(({ type, value: part }) => [type, part]));
  let text;
  if (current.workspace.dateFormat === "YYYY-MM-DD") text = `${parts.year}-${parts.month}-${parts.day}`;
  else if (current.workspace.dateFormat === "DD/MM/YYYY") text = `${parts.day}/${parts.month}/${parts.year}`;
  else text = new Intl.DateTimeFormat("en-GB", { timeZone: "Asia/Kolkata", day: "2-digit", month: "short", year: "numeric" }).format(date);
  return withTime ? `${text}, ${new Intl.DateTimeFormat("en-IN", { timeZone: "Asia/Kolkata", hour: "numeric", minute: "2-digit" }).format(date)}` : text;
}
