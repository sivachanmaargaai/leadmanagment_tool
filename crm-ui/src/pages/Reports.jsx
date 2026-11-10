import { useSettings } from "../context/SettingsContext";
import { canAccessQuotations } from "../lib/permissions";
import { useEffect, useState } from "react";
import { Download, RefreshCw, Filter } from "lucide-react";
import { divisionLabel, divisions } from "../data/crm";
import { Button, Card, CardHeading } from "../components/ui";
import ReportTable from "../components/reports/ReportTable";
import ReportBars from "../components/reports/ReportBars";
import { getReports } from "../services/reportsApi";
import { csvText, datePreset, exportReportPdf, saveFile } from "../lib/reports";
import { money } from "../lib/quotationPdf";
import { displayDate } from "../lib/runtimeSettings";

const initial = { startDate: "", endDate: "", division: "", includeTestData: false, leadStatus: "", quoteStatus: "", followUpStatus: "" };
const field = "min-h-10 min-w-0 w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-xs text-slate-950 outline-none focus:border-teal-600 focus:ring-2 focus:ring-teal-100";
const tabs = ["Leads", "Divisions", "Follow-ups", "Quotations", "Lead sources"];
const dateText = (value) => displayDate(value, true);
const columns = {
  Leads: [{ key: "customer", label: "Customer" }, { key: "division", label: "Division" }, { key: "status", label: "Status" }, { key: "priority", label: "Priority" }, { key: "source", label: "Source" }, { key: "reference", label: "Referred by" }, { key: "createdAt", label: "Created (IST)", render: (x) => dateText(x.createdAt), exportValue: (x) => dateText(x.createdAt) }],
  Divisions: [{ key: "name", label: "Division" }, { key: "total", label: "Leads" }, { key: "won", label: "Won" }, { key: "lost", label: "Lost" }, { key: "conversionRate", label: "Conversion %" }],
  "Follow-ups": [{ key: "customer", label: "Customer" }, { key: "purpose", label: "Purpose" }, { key: "division", label: "Division" }, { key: "assignedTo", label: "Assigned to" }, { key: "dueAt", label: "Due (IST)", render: (x) => dateText(x.dueAt), exportValue: (x) => dateText(x.dueAt) }, { key: "status", label: "Status", render: (x) => x.overdue ? <span className="font-semibold text-rose-800">Overdue</span> : x.status, exportValue: (x) => x.overdue ? "Overdue" : x.status }],
  Quotations: [{ key: "number", label: "Quotation" }, { key: "customer", label: "Customer" }, { key: "division", label: "Division" }, { key: "date", label: "Date" }, { key: "status", label: "Status" }, { key: "amount", label: "Amounts by billing period", render: (x) => Object.entries(x.totals).map(([billing, amount]) => <div key={billing} className="whitespace-nowrap leading-6">{money(amount.total, x.currency)} · {billing}</div>), exportValue: (x) => Object.entries(x.totals).map(([billing, amount]) => `${x.currency} ${amount.total.toFixed(2)} ${billing}`).join("; ") }],
  "Lead sources": [{ key: "name", label: "Lead source" }, { key: "total", label: "Leads" }, { key: "won", label: "Won" }, { key: "lost", label: "Lost" }, { key: "conversionRate", label: "Conversion %" }],
};
const referralColumns = [{ key: "name", label: "Referred by" }, { key: "company", label: "Company / network" }, { key: "source", label: "Source" }, { key: "total", label: "Leads" }, { key: "won", label: "Won" }];

function AcceptedValue({ rows }) {
  return <div className="space-y-2 text-xs">{rows.length ? rows.map((row) => <p key={`${row.currency}-${row.billing}`} className="flex flex-wrap justify-between gap-2"><span className="text-slate-700">{row.billing} · {row.currency}</span><strong className="text-teal-950">{money(row.total, row.currency)}</strong></p>) : <p className="text-slate-600">No accepted quotations in this period.</p>}</div>;
}

export default function Reports({ onNavigate }) {
  const { user } = useSettings();
  const canQuotes = canAccessQuotations(user);
  const [draft, setDraft] = useState(initial);
  const [applied, setApplied] = useState(initial);
  const [preset, setPreset] = useState("all");
  const [selectedTab, setTab] = useState("Leads");
  const tab = selectedTab === "Quotations" && !canQuotes ? "Leads" : selectedTab;
  const [refresh, setRefresh] = useState(0);
  const [result, setResult] = useState(null);
  const [exporting, setExporting] = useState(false);
  const [exportError, setExportError] = useState("");
  const requestKey = JSON.stringify({ ...applied, refresh });
  const current = result?.key === requestKey ? result : null;
  const data = current?.data;
  const loading = !current;
  const statusField = tab === "Quotations" ? "quoteStatus" : tab === "Follow-ups" ? "followUpStatus" : "leadStatus";
  const statuses = tab === "Quotations" ? ["Draft", "Sent", "Accepted", "Rejected", "Expired"] : tab === "Follow-ups" ? ["Pending", "Completed"] : ["New", "In Progress", "Follow-up", "Won", "Lost"];
  const invalidDates = draft.startDate && draft.endDate && draft.startDate > draft.endDate;

  useEffect(() => {
    let active = true;
    const controller = new AbortController();
    getReports(JSON.parse(requestKey), controller.signal, canQuotes)
      .then((reports) => { if (active) setResult({ key: requestKey, data: reports }); })
      .catch((error) => { if (active) setResult({ key: requestKey, error: error.message }); });
    return () => { active = false; controller.abort(); };
  }, [requestKey, canQuotes]);

  function apply(event) {
    event?.preventDefault();
    if (invalidDates) return;
    setApplied({ ...draft }); setRefresh((value) => value + 1); setExportError("");
  }
  function quickFilter(key, value) {
    const filters = { ...applied, [key]: value };
    setDraft(filters); setApplied(filters); setPreset("custom");
  }
  function reset() { setDraft(initial); setApplied(initial); setPreset("all"); setRefresh((value) => value + 1); setExportError(""); }
  function choosePreset(value) { setPreset(value); const range = datePreset(value); if (range) setDraft((old) => ({ ...old, ...range })); }

  const rows = !data ? [] : tab === "Leads" ? data.leads.rows : tab === "Divisions" ? data.leads.byDivision : tab === "Follow-ups" ? data["follow-ups"].rows : tab === "Quotations" ? data.sales.rows : data.leads.bySource;
  const basis = data ? (tab === "Quotations" ? data.sales.dateBasis : tab === "Follow-ups" ? data["follow-ups"].dateBasis : data.leads.dateBasis) : "";
  const notes = `${applied.startDate || "All dates"} to ${applied.endDate || "present"}; ${divisionLabel(applied.division || "All divisions")}; ${applied[statusField] || "All statuses"}; Test data: ${applied.includeTestData ? "included" : "excluded"}. ${basis}. Accepted values are quotation commitments, not received revenue. Export includes all report rows; table search is for browsing only.`;

  async function exportData(format) {
    setExporting(true); setExportError("");
    try {
      if (format === "csv") saveFile(new Blob([csvText(columns[tab], rows)], { type: "text/csv;charset=utf-8" }), `engen-${tab.toLowerCase().replaceAll(" ", "-")}-report.csv`);
      else await exportReportPdf(tab, columns[tab], rows, notes);
    } catch (error) { setExportError(error.message || "Could not export the report."); }
    finally { setExporting(false); }
  }

  return <div className="space-y-4">
    <p className="text-xs leading-6 text-slate-700">Track lead progress, follow-ups and quotation performance across your divisions.</p>
    <Card><form onSubmit={apply} className="space-y-3 p-4">
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-5">
        <label className="space-y-1 text-xs font-semibold text-slate-800">Period<select className={field} value={preset} onChange={(event) => choosePreset(event.target.value)}><option value="all">All time</option><option value="today">Today</option><option value="week">This week</option><option value="month">This month</option><option value="custom">Custom dates</option></select></label>
        <label className="space-y-1 text-xs font-semibold text-slate-800">From<input type="date" className={field} value={draft.startDate} onChange={(event) => { setPreset("custom"); setDraft({ ...draft, startDate: event.target.value }); }} /></label>
        <label className="space-y-1 text-xs font-semibold text-slate-800">To<input type="date" className={field} value={draft.endDate} min={draft.startDate || undefined} onChange={(event) => { setPreset("custom"); setDraft({ ...draft, endDate: event.target.value }); }} /></label>
        <label className="space-y-1 text-xs font-semibold text-slate-800">Division<select className={field} value={draft.division} onChange={(event) => setDraft({ ...draft, division: event.target.value })}><option value="">All divisions</option>{divisions.map((name) => <option key={name} value={name}>{divisionLabel(name)}</option>)}</select></label>
        <label className="space-y-1 text-xs font-semibold text-slate-800">{tab === "Quotations" ? "Quotation" : tab === "Follow-ups" ? "Follow-up" : "Lead"} status<select className={field} value={draft[statusField]} onChange={(event) => setDraft({ ...draft, [statusField]: event.target.value })}><option value="">All statuses</option>{statuses.map((name) => <option key={name}>{name}</option>)}</select></label>
      </div>
      <div className="flex flex-wrap items-center justify-between gap-3"><label className="flex min-h-10 cursor-pointer items-center gap-2 text-xs font-semibold text-slate-800"><input type="checkbox" checked={draft.includeTestData} onChange={(event) => setDraft({ ...draft, includeTestData: event.target.checked })} className="size-4 accent-teal-800" />Include test data</label><div className="flex flex-wrap gap-2"><Button variant="secondary" onClick={reset}>Reset</Button><Button type="submit" disabled={Boolean(invalidDates)}><Filter size={15} />Apply filters</Button></div></div>
      {invalidDates && <p role="alert" className="text-xs text-rose-800">From date must be on or before To date.</p>}
    </form></Card>

    {loading ? <Card><p role="status" className="p-8 text-center text-sm text-slate-700">Loading reports...</p></Card> : current.error ? <Card><div role="alert" className="space-y-3 p-5 text-sm text-rose-900"><p>{current.error}</p><Button variant="secondary" onClick={() => setRefresh((value) => value + 1)}><RefreshCw size={15} />Retry reports</Button></div></Card> : <>
      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        {[["Total leads", data.summary.totals.totalLeads], ["Won leads", data.summary.totals.wonLeads], ["Conversion rate", `${data.summary.totals.conversionRate}%`], ["Overdue follow-ups", data.summary.totals.overdueFollowUps]].map(([label, value]) => <Card key={label}><div className="p-4"><p className="text-xs font-semibold text-slate-700">{label}</p><strong className="mt-2 block text-2xl text-slate-950">{value}</strong></div></Card>)}
      </div>
      {canQuotes && <Card><CardHeading title="Accepted quotation value" description="Amounts include quoted tax. One-time and recurring values, and different currencies, stay separate. These are not received payments." /><div className="px-4 pb-4"><AcceptedValue rows={data.summary.acceptedValue} /></div></Card>}
      <p className="text-[11px] leading-5 text-slate-600">Conversion = Won ÷ (Won + Lost). Summary cards use date/division/test-data filters across all statuses. Leads use created date, quotations use quotation date, follow-ups use due date. All date boundaries use IST.</p>

      <div role="tablist" aria-label="Report type" className="flex gap-2 overflow-x-auto pb-1">{tabs.filter((name) => name !== "Quotations" || canQuotes).map((name) => <button key={name} id={`tab-${name.replaceAll(" ", "-")}`} type="button" role="tab" aria-selected={tab === name} aria-controls="report-panel" onClick={() => { setTab(name); setExportError(""); }} className={`min-h-10 shrink-0 rounded-lg border px-4 py-2 text-xs font-semibold transition-colors focus-visible:outline-2 focus-visible:outline-teal-700 ${tab === name ? "border-teal-800 bg-teal-800 text-white shadow-sm" : "border-slate-200 bg-white text-slate-800 hover:bg-teal-50"}`}>{name}</button>)}</div>
      <div id="report-panel" role="tabpanel" aria-labelledby={`tab-${tab.replaceAll(" ", "-")}`} className="space-y-4">
        <div className="grid gap-3 md:grid-cols-2">
          {tab === "Leads" && <><ReportBars title="Lead status" items={data.leads.byStatus} onSelect={(name) => quickFilter("leadStatus", name)} /><ReportBars title="Lead priority" items={data.leads.byPriority} /><ReportBars title="Monthly lead trend" items={data.leads.trend} valueKey="total" /></>}
          {tab === "Divisions" && <><ReportBars title="Leads by division" items={data.leads.byDivision} valueKey="total" onSelect={(name) => quickFilter("division", name)} /><ReportBars title="Won leads by division" items={data.leads.byDivision} valueKey="won" /></>}
          {tab === "Follow-ups" && <><ReportBars title="Follow-up progress" items={[{ name: "Pending", count: data["follow-ups"].summary.pending }, { name: "Completed", count: data["follow-ups"].summary.completed }]} onSelect={(name) => quickFilter("followUpStatus", name)} /><ReportBars title="Overdue tasks by staff" items={data["follow-ups"].byStaff} valueKey="overdue" /></>}
          {tab === "Quotations" && <><ReportBars title="Quotation status" items={data.sales.byStatus} onSelect={(name) => quickFilter("quoteStatus", name)} /><Card><CardHeading title="Accepted values for this quotation filter" /><div className="px-4 pb-4"><AcceptedValue rows={data.sales.acceptedValue} /></div></Card></>}
          {tab === "Lead sources" && <><ReportBars title="Leads by source" items={data.leads.bySource} valueKey="total" /><ReportBars title="Won leads by source" items={data.leads.bySource} valueKey="won" /></>}
        </div>
        <Card><CardHeading title={`${tab} report`} description={`${basis}. Table search is for browsing; exports include all ${rows.length} report rows.`}><div className="flex flex-wrap gap-2"><Button variant="secondary" disabled={exporting || !rows.length} onClick={() => exportData("csv")}><Download size={15} />CSV for Excel</Button><Button variant="secondary" disabled={exporting || !rows.length} onClick={() => exportData("pdf")}><Download size={15} />{exporting ? "Exporting..." : "PDF"}</Button>{onNavigate && <Button variant="secondary" onClick={() => onNavigate(tab === "Quotations" ? "Quotations" : tab === "Follow-ups" ? "Follow-ups" : "Leads")}>Open module</Button>}</div></CardHeading>
          {exportError && <p role="alert" className="px-4 pb-3 text-xs text-rose-900">{exportError}</p>}
          <ReportTable key={`${requestKey}-${tab}`} rows={rows} columns={columns[tab]} />
        </Card>
        {tab === "Lead sources" && <Card><CardHeading title="Referral & known-network contacts" description="Reference contacts and their lead outcomes." /><ReportTable key={`refs-${requestKey}`} rows={data.leads.referrals} columns={referralColumns} /></Card>}
        {tab === "Follow-ups" && <Card><CardHeading title="Staff workload" /><ReportTable key={`staff-${requestKey}`} rows={data["follow-ups"].byStaff} columns={[{ key: "name", label: "Staff" }, { key: "total", label: "Total" }, { key: "pending", label: "Pending" }, { key: "completed", label: "Completed" }, { key: "overdue", label: "Overdue" }]} /></Card>}
      </div>
    </>}
  </div>;
}
