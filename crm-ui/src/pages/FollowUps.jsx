import useServerPage from "../hooks/useServerPage";
import useWorkspaceData from "../hooks/useWorkspaceData";
import { getFollowUpsPage, createFollowUp, updateFollowUp } from "../services/followUpsApi";
import Pagination from "../components/Pagination";
import { useState } from "react";
import { CalendarClock, Plus, Search, Check, History, RefreshCw, Clock3, CheckCheck, AlertCircle } from "lucide-react";
import { divisionLabel, divisions } from "../data/crm";
import { Avatar, Button, Card, CardHeading, EmptyState, IconButton } from "../components/ui";
import Modal from "../components/Modal";
import FollowUpEditor from "../components/followups/FollowUpEditor";
import { formatFollowUpDate, isOverdue } from "../lib/followUps";

const selectClass = "rounded-lg border border-slate-300 bg-white px-3 py-2 text-xs font-medium text-slate-900 outline-none focus:border-teal-600 focus:ring-2 focus:ring-teal-100";
const summaryItems = [
  { name: "Today", icon: CalendarClock, tone: "bg-teal-50 text-teal-800", caption: "Pending tasks scheduled today" },
  { name: "Overdue", icon: AlertCircle, tone: "bg-rose-50 text-rose-800", caption: "Past due and still pending" },
  { name: "Upcoming", icon: Clock3, tone: "bg-lime-100 text-lime-900", caption: "Scheduled after today" },
  { name: "Completed", icon: CheckCheck, tone: "bg-emerald-50 text-emerald-800", caption: "Conversations recorded" },
];

export default function FollowUps({ now, onChanged }) {
  const [tab, setTab] = useState("All");
  const [search, setSearch] = useState("");
  const [division, setDivision] = useState("All divisions");
  const [staff, setStaff] = useState("All staff");
  const [date, setDate] = useState("");
  const [editor, setEditor] = useState(null);
  const [history, setHistory] = useState(null);
  const [notice, setNotice] = useState("");
  const pagination = useServerPage(getFollowUpsPage, { division, assignedTo: staff, date, q: search, view: tab });
  const { rows: pageRows, loading, error: storageError, refresh: onRefresh } = pagination;
  const metrics = useWorkspaceData("metrics", division, notice, staff);
  const timeline = (history?.history || []).map((entry) => ({ ...entry, purpose: history.purpose })).sort((a, b) => Date.parse(b.at) - Date.parse(a.at));
  async function save(record, next) {
    if (record.version) await updateFollowUp(record, next);
    else await createFollowUp(record);
    onRefresh(); onChanged?.();
    setEditor(null);
    setNotice(`Follow-up saved at ${new Date().toLocaleTimeString()}.`);
  }

  return <div className="space-y-4">
    <div className="flex flex-wrap items-center justify-between gap-4">
      <p className="max-w-xl text-xs leading-6 text-slate-700">Plan the next conversation. Track who introduced the customer.<br />All times are IST · Records are saved to the database.</p>
      <Button disabled={loading || Boolean(storageError)} onClick={() => setEditor({ mode: "schedule" })}><Plus size={17} />Schedule follow-up</Button>
    </div>

    <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
      {summaryItems.map(({ name, icon: Icon, tone, caption }) => <button key={name} type="button" onClick={() => setTab(name)} aria-pressed={tab === name}
        className={`rounded-2xl border bg-white p-4 text-left shadow-sm shadow-slate-900/8 transition-shadow duration-200 hover:shadow-md focus-visible:outline-2 focus-visible:outline-teal-700 ${tab === name ? "border-teal-600 ring-1 ring-teal-600" : "border-slate-200"}`}>
        <span className="flex items-center justify-between gap-2"><span className="text-xs font-semibold text-slate-700">{name}</span><span className={`flex size-9 items-center justify-center rounded-xl ${tone}`}><Icon size={18} /></span></span>
        <strong className="mt-2 block text-2xl font-bold text-slate-950">{metrics.data?.followUps?.[name] ?? "…"}</strong>
        <span className="mt-2 block text-[11px] leading-5 text-slate-600">{caption}</span>
      </button>)}
    </div>

    {storageError && <p role="alert" className="rounded-xl bg-rose-50 p-4 text-sm text-rose-900">{storageError} <button type="button" className="ml-2 font-semibold underline" onClick={onRefresh}>Retry</button></p>}
    {metrics.error && <p role="alert" className="text-xs text-rose-800">Summary: {metrics.error}</p>}
    {loading && <p role="status" className="rounded-xl bg-teal-50 p-3 text-xs text-teal-950">Loading follow-ups from the database...</p>}
    {notice && <p role="status" className="rounded-xl border border-teal-200 bg-teal-50 p-4 text-xs text-teal-950">{notice}</p>}

    <Card>
      <CardHeading title="Follow-up register" description="Customer tasks, reference contacts and conversation history." />
      <div className="flex flex-wrap gap-2 border-y border-slate-100 px-5 py-3" aria-label="Follow-up views">
        {["All", "Today", "Overdue", "Upcoming", "Completed"].map((name) => <button key={name} type="button" aria-pressed={tab === name} onClick={() => setTab(name)}
          className={`rounded-lg px-3 py-2 text-xs font-semibold transition-colors ${tab === name ? "bg-teal-900 text-white" : "text-slate-700 hover:bg-teal-50"}`}>{name}</button>)}
      </div>
      <div className="flex flex-wrap gap-3 px-4 py-3">
        <label className="flex min-w-0 basis-full sm:basis-44 flex-1 items-center gap-2 rounded-lg border border-slate-300 px-3 py-2 text-slate-700 focus-within:ring-2 focus-within:ring-teal-100">
          <Search size={16} /><input aria-label="Search follow-ups" placeholder="Customer, purpose or reference..." value={search} onChange={(event) => setSearch(event.target.value)} className="w-full bg-transparent text-xs outline-none placeholder:text-slate-500" />
        </label>
        <select aria-label="Filter follow-ups by division" value={division} onChange={(event) => setDivision(event.target.value)} className={selectClass}><option>All divisions</option>{divisions.map((name) => <option key={name} value={name}>{divisionLabel(name)}</option>)}</select>
        <input aria-label="Filter follow-ups by staff" placeholder="Exact staff name" value={staff === "All staff" ? "" : staff} onChange={(event) => setStaff(event.target.value || "All staff")} maxLength={120} className={selectClass} />
        <input aria-label="Filter follow-ups by date" type="date" value={date} onChange={(event) => setDate(event.target.value)} className={selectClass} />
        {(search || date || staff !== "All staff" || division !== "All divisions" || tab !== "All") && <Button variant="secondary" onClick={() => { setSearch(""); setDate(""); setStaff("All staff"); setDivision("All divisions"); setTab("All"); }}>Clear filters</Button>}
      </div>
      <div className="grid gap-3 px-3 pb-3 sm:grid-cols-2 lg:hidden">
        {pageRows.map((item) => {
          const overdue = isOverdue(item, now);
          return <article key={item.id} className={`min-w-0 rounded-xl border p-3 shadow-sm shadow-slate-900/5 ${overdue ? "border-rose-200 bg-rose-50/30" : "border-slate-200 bg-white"}`}>
            <div className="flex items-start gap-2.5"><Avatar name={item.customer} /><div className="min-w-0 flex-1"><button type="button" onClick={() => setHistory(item)} className="break-words text-left text-xs font-bold text-slate-950 hover:text-teal-800">{item.customer}</button><p className="mt-1 text-[11px] text-slate-700">{divisionLabel(item.division)}</p></div><span className={`shrink-0 rounded-md px-2 py-1 text-[10px] font-semibold ${item.status === "Completed" ? "bg-emerald-50 text-emerald-900" : overdue ? "bg-rose-100 text-rose-900" : "bg-amber-50 text-amber-900"}`}>{overdue ? "Overdue" : item.status}</span></div>
            <p className="my-3 break-words text-xs font-medium leading-5 text-slate-900">{item.purpose}</p>
            <p className={`flex items-start gap-2 text-[11px] leading-5 ${overdue ? "font-semibold text-rose-800" : "text-slate-700"}`}><CalendarClock size={14} className="mt-0.5 shrink-0" />{formatFollowUpDate(item.dueAt)} IST</p>
            <dl className="mt-3 space-y-1.5 text-[11px]"><div className="flex justify-between gap-3"><dt className="shrink-0 text-slate-600">Referred by</dt><dd className="min-w-0 break-words text-right font-semibold text-teal-900">{item.referredBy?.name || "Not specified"}</dd></div><div className="flex justify-between gap-3"><dt className="text-slate-600">Assigned to</dt><dd className="min-w-0 break-words text-right text-slate-900">{item.assignedTo}</dd></div></dl>
            <div className="mt-3 flex flex-wrap items-center justify-between gap-2 border-t border-slate-100 pt-2"><span className={`text-[11px] font-semibold ${item.priority === "High" ? "text-rose-800" : "text-slate-700"}`}>{item.priority} · {item.type}</span><div className="flex gap-1">
              {item.status === "Pending" && <><IconButton aria-label={`Complete ${item.purpose}`} onClick={() => setEditor({ mode: "complete", record: item })}><Check size={17} /></IconButton><IconButton aria-label={`Reschedule ${item.purpose}`} onClick={() => setEditor({ mode: "reschedule", record: item })}><RefreshCw size={16} /></IconButton></>}
              <IconButton aria-label={`History for ${item.customer}`} onClick={() => setHistory(item)}><History size={17} /></IconButton>
            </div></div>
          </article>;
        })}
      </div>
      <div className="hidden overflow-x-auto lg:block">
        <table className="w-full whitespace-nowrap text-left">
          <thead className="border-y border-slate-200 bg-slate-50 text-[10px] uppercase tracking-wide text-slate-700"><tr>{["Customer", "Referred by", "Purpose", "Date & time · IST", "Assigned to", "Priority", "Status", "Actions"].map((name) => <th key={name} className="px-5 py-3">{name}</th>)}</tr></thead>
          <tbody className="divide-y divide-slate-100">{pageRows.map((item) => {
            const overdue = isOverdue(item, now);
            return <tr key={item.id} className={`text-xs text-slate-800 transition-colors ${overdue ? "bg-rose-50/40 hover:bg-rose-50" : "hover:bg-teal-50/40"}`}>
              <td className="px-5 py-4"><button type="button" onClick={() => setHistory(item)} className="flex items-center gap-3 text-left hover:text-teal-800"><Avatar name={item.customer} /><span><strong className="block font-semibold">{item.customer}</strong><small className="mt-1 block text-slate-600">{divisionLabel(item.division)}</small></span></button></td>
              <td className="px-5 py-4"><strong className="block font-semibold">{item.referredBy?.name || "Not specified"}</strong><small className="mt-1 block text-slate-600">{item.referredBy?.company || item.leadSource || "—"}</small></td>
              <td className="px-5 py-4"><span className="block max-w-55 truncate" title={item.purpose}>{item.purpose}</span><small className="mt-1 block text-slate-600">{item.type}</small></td>
              <td className={`px-5 py-4 ${overdue ? "font-semibold text-rose-800" : ""}`}>{formatFollowUpDate(item.dueAt)}</td>
              <td className="px-5 py-4">{item.assignedTo}</td>
              <td className={`px-5 py-4 font-semibold ${item.priority === "High" ? "text-rose-800" : item.priority === "Medium" ? "text-amber-800" : "text-emerald-800"}`}>{item.priority}</td>
              <td className="px-5 py-4"><span className={`rounded-md px-2 py-1 text-[10px] font-semibold ${item.status === "Completed" ? "bg-emerald-50 text-emerald-900" : overdue ? "bg-rose-100 text-rose-900" : "bg-amber-50 text-amber-900"}`}>{overdue ? "Overdue" : item.status}</span></td>
              <td className="px-5 py-4"><div className="flex items-center gap-1">
                {item.status === "Pending" && <><IconButton aria-label={`Complete ${item.purpose}`} title="Complete" onClick={() => setEditor({ mode: "complete", record: item })}><Check size={17} /></IconButton><IconButton aria-label={`Reschedule ${item.purpose}`} title="Reschedule" onClick={() => setEditor({ mode: "reschedule", record: item })}><RefreshCw size={16} /></IconButton></>}
                <IconButton aria-label={`History for ${item.customer}`} title="Customer history" onClick={() => setHistory(item)}><History size={17} /></IconButton>
              </div></td>
            </tr>;
          })}</tbody>
        </table>
      </div>
      {!pageRows.length && <EmptyState icon={CalendarClock} title={pagination.total ? "No matching follow-ups" : "Your next conversation starts here"} description={pagination.total ? "Try another view, date or reference name." : "Schedule a follow-up against a lead. Its reference contact will appear automatically."} />}
      <footer className="border-t border-slate-200 px-5 py-4 text-xs text-slate-600">{pagination.total} matching follow-up(s) · Today includes overdue tasks due today.</footer>
    </Card>

    <Pagination pagination={pagination} />
    {editor && <FollowUpEditor mode={editor.mode} record={editor.record} onClose={() => setEditor(null)} onSave={save} />}
    {history && <Modal title={`${history.customer} · Task history`} onClose={() => setHistory(null)}>
      <div className="p-6">
        <div className="mb-6 rounded-xl bg-teal-50 p-4 text-xs leading-6 text-slate-800">
          <strong className="block text-sm text-teal-950">{history.customer}</strong>
          <p>{divisionLabel(history.division)} · Reference: {history.referredBy?.name || "Not specified"}</p>
          {history.referredBy && <p>{[history.referredBy.company, history.referredBy.phone, history.referredBy.email].filter(Boolean).join(" · ")}</p>}
        </div>
        <ol className="space-y-5 border-l border-teal-200 pl-5">{timeline.map((entry) => <li key={entry.id}>
          <p className="text-[11px] font-semibold text-teal-800">{formatFollowUpDate(entry.at)} IST</p>
          <strong className="mt-1 block text-xs text-slate-950">{entry.purpose}</strong>
          <p className="mt-2 whitespace-pre-wrap text-xs leading-6 text-slate-700">{entry.message}</p>
        </li>)}</ol>
      </div>
    </Modal>}
  </div>;
}
