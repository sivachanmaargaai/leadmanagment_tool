import { defaultSettings } from "../../src/lib/runtimeSettings.js";

export const owner = { id: "ui-owner", name: "UI Test Owner", email: "owner@fixture.test", role: "Admin", isOwner: true, isActive: true, canAccessQuotations: true, version: 1, createdAt: "2026-11-05T00:00:00Z" };
export const staff = { ...owner, id: "ui-staff", name: "UI Test Staff", email: "staff@fixture.test", role: "Staff", isOwner: false, canAccessQuotations: false };
const longName = "Embedded intelligence and industrial IoT firmware engineering requirements for a manufacturing customer";
const leads = Array.from({ length: 12 }, (_, index) => ({ id: `fixture-lead-${index}`, customer: index === 0 ? longName : `Fixture customer ${index + 1}`, contact: "Test contact", division: "MMC", description: "Embedded hardware and firmware development", status: "New", priority: "Medium", leadSource: "Direct Enquiry", referredBy: null, referenceNotes: "", version: 1, assigneeUserId: null, createdAt: "2026-11-05T00:00:00Z", updatedAt: "2026-11-05T00:00:00Z" }));
export const customer = { id: "fixture-customer", name: longName, type: "Company", divisions: ["MMC"], contacts: [{ name: "Fixture contact", designation: "Engineer", phone: "1234567890", email: "fixture-contact@fixture.test" }], address: "Test address", city: "Chennai", state: "Tamil Nadu", postcode: "600001", gst: "", assignedTo: owner.name, notes: "Fixture notes", leadSource: "Direct Enquiry", referredBy: null, referenceNotes: "", aliases: [], history: [], version: 1, assigneeUserId: owner.id, createdAt: "2026-11-05T00:00:00Z", updatedAt: "2026-11-05T00:00:00Z" };
export const quote = { id: "fixture-quote", number: "FIXTURE-001", customer: longName, contact: "Fixture contact", address: "Test address", division: "MMC", date: "2026-11-05", validUntil: "2026-12-05", status: "Draft", currency: "INR", tax: 0, terms: "Fixture payment terms", billing: "One-time", amount: 100, items: [{ description: "Firmware", quantity: 1, rate: 100, billing: "One-time" }], totals: { "One-time": { subtotal: 100, tax: 0, total: 100 } }, source: "Created", version: 1, createdAt: "2026-11-05T00:00:00Z", updatedAt: "2026-11-05T00:00:00Z", versions: [{ id: "fixture-pdf", name: "fixture.pdf", revision: 1, size: 100, uploadedAt: "2026-11-05T00:00:00Z", pdfPath: "/api/quotations/fixture-quote/versions/fixture-pdf/pdf", snapshot: {} }] };
export const followUp = { id: "fixture-follow-up", leadId: leads[0].id, customer: longName, division: "MMC", purpose: "Firmware quotation discussion with the customer engineering team", type: "Call", dueAt: "2026-12-05T10:00:00Z", assignedTo: owner.name, priority: "Medium", reminderMinutes: 30, notes: "Fixture discussion", status: "Pending", outcome: "", completionNotes: "", completedAt: null, history: [], version: 1, leadSource: "Direct Enquiry", referredBy: null, createdAt: "2026-11-05T00:00:00Z", updatedAt: "2026-11-05T00:00:00Z" };

export async function mockCrm(page, preferences = {}, activeUser = owner) {
  const errors = [];
  page.on("pageerror", (error) => errors.push(error.message));
  const settings = defaultSettings();
  settings.profile = { name: activeUser.name, email: activeUser.email, phone: "", designation: "Administrator" };
  settings.canManageShared = activeUser.isOwner;
  settings.canAccessQuotations = activeUser.role === "Admin" || activeUser.canAccessQuotations === true;
  if (!settings.canAccessQuotations) { delete settings.quotation; settings.notifications.quotationExpiry = false; }
  settings.notifications.sound = false;
  Object.assign(settings.workspace, preferences);
  const reportBase = { filters: {}, generatedAt: "2026-11-05T00:00:00Z", timezone: "Asia/Kolkata", dateBasis: "Fixture" };
  const metrics = { leads: { total: 12, active: 12, won: 0, high: 0, pipeline: { New: 12 } }, quotations: { Total: 1, Draft: 1 }, followUps: { All: 1, Today: 0, Overdue: 0, Upcoming: 1, Completed: 0 }, customers: { "Total customers": 1, Prospects: 1, "Converted customers": 0 } };
  await page.route("**/api/**", async (route) => {
    const request = route.request();
    const url = new URL(request.url());
    const path = url.pathname;
    let data;
    if (path === "/api/auth/refresh") data = { accessToken: "isolated-ui-fixture-token", tokenType: "Bearer", expiresIn: 900, user: activeUser };
    else if (request.method() !== "GET") {
      errors.push(`Unexpected fixture mutation: ${request.method()} ${path}`);
      return route.fulfill({ status: 409, json: { detail: "UI fixture is read-only" } });
    } else if (path === "/api/auth/me") data = activeUser;
    else if (path === "/api/settings") data = settings;
    else if (path === "/api/workspace/metrics") data = metrics;
    else if (path === "/api/workspace/overview") data = { metrics, recentLeads: leads.slice(0, 5), queue: [followUp], alertLeads: [], alertFollowUps: [], alertQuotes: [] };
    else if (path === `/api/customers/${customer.id}`) data = { ...customer, stage: "Prospect", leadCount: 12 };
    else if (path === `/api/quotations/${quote.id}`) data = quote;
    else if (path === "/api/permissions") data = { version: 1, roles: { Admin: { quotations: true, readOnly: true }, Staff: { quotations: false, readOnly: false } } };
    else if (path === "/api/users") data = { users: [owner, staff], canManageUsers: true, canManageQuotationAccess: true, adminCount: 1, adminLimit: 2, scope: "All users" };
    else if (path === "/api/access/assignments") data = { module: url.searchParams.get("module"), users: [owner, staff], hasMore: false, records: leads.map((lead) => ({ id: lead.id, label: lead.customer, assigneeUserId: null, version: 1 })) };
    else if (["/api/leads", "/api/customers", "/api/quotations", "/api/follow-ups"].includes(path)) {
      const records = path === "/api/leads" ? leads : path === "/api/customers" ? [customer] : path === "/api/quotations" ? [quote] : [followUp];
      const q = (url.searchParams.get("q") || "").toLowerCase();
      const matching = records.filter((record) => JSON.stringify(record).toLowerCase().includes(q));
      const number = Number(url.searchParams.get("page") || 1), size = Number(url.searchParams.get("pageSize") || 100);
      const pages = Math.max(1, Math.ceil(matching.length / size));
      data = { items: matching.slice((number - 1) * size, number * size), total: matching.length, page: number, pageSize: size, pages, hasMore: number < pages };
    } else if (path === "/api/ops/status") data = { status: "warning", issues: ["backup-not-configured"], database: { reachable: true, schemaCurrent: true }, backup: { status: "not-configured", restoreVerifiedAt: null }, metrics: { requests: 12, recentServerErrors: 0, slowRequests: 0 } };
    else if (path === "/api/reports/summary") data = { ...reportBase, totals: { totalLeads: 12, wonLeads: 0, lostLeads: 0, conversionRate: 0, overdueFollowUps: 0, totalQuotations: 1, acceptedQuotations: 0 }, acceptedValue: [] };
    else if (path === "/api/reports/leads") data = { ...reportBase, rows: leads, byStatus: [], byPriority: [], byDivision: [], bySource: [], trend: [], referrals: [] };
    else if (path === "/api/reports/sales") data = { ...reportBase, rows: [], byStatus: [], acceptedValue: [] };
    else if (path === "/api/reports/follow-ups") data = { ...reportBase, rows: [], summary: { total: 0, pending: 0, completed: 0, overdue: 0 }, byStaff: [], byType: [] };
    else {
      errors.push(`Unhandled fixture API: ${path}`);
      return route.fulfill({ status: 404, json: { detail: "No matching fixture" } });
    }
    if (!settings.canAccessQuotations) {
      if (path === "/api/workspace/metrics") { data = { ...data }; delete data.quotations; }
      if (path === "/api/workspace/overview") { data = { ...data, metrics: { ...data.metrics } }; delete data.metrics.quotations; delete data.alertQuotes; }
      if (path === "/api/reports/summary") { data = { ...data, totals: { ...data.totals }, canAccessQuotations: false }; delete data.totals.totalQuotations; delete data.totals.acceptedQuotations; delete data.acceptedValue; }
    }
    await route.fulfill({ json: data });
  });
  return errors;
}
