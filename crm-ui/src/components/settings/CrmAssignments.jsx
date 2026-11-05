import { useEffect, useRef, useState } from "react";
import { getAssignments, assignRecord } from "../../services/accessApi";
import { Button } from "../ui";

export default function CrmAssignments() {
  const [module, setModule] = useState("leads");
  const [offset, setOffset] = useState(0);
  const [revision, setRevision] = useState(0);
  const [state, setState] = useState(null);
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState("");
  const lock = useRef(false);
  const key = `${module}:${offset}:${revision}`;
  const current = state?.key === key ? state : null;
  useEffect(() => {
    const controller = new AbortController();
    getAssignments(module, offset, controller.signal).then((data) => setState({ key, data })).catch((error) => {
      if (!controller.signal.aborted) setState({ key, error: error.message });
    });
    return () => controller.abort();
  }, [module, offset, revision, key]);

  async function save(record, value) {
    if (lock.current) return;
    lock.current = true; setBusy(true); setNotice("");
    try { await assignRecord(module, record, value); setNotice("Assignment saved. Lead follow-ups use the same access. Refresh open CRM pages to load current assignments."); }
    catch (error) { setNotice(error.message); }
    finally { lock.current = false; setBusy(false); setRevision((value) => value + 1); }
  }
  return <section className="w-full min-w-0 rounded-2xl border border-slate-200 bg-white p-4 text-slate-950 shadow-sm sm:p-5">
    <h3 className="text-lg font-bold">CRM record access</h3>
    <p className="mt-2 text-xs leading-6 text-slate-700">Administrators see all records. Staff see their assigned records. Follow-ups inherit lead access. Customer profiles and quotations are assigned separately; matching names never grant access. Unassigned records are Admin-only.</p>
    <label className="mt-4 block text-xs font-semibold">Record type<select disabled={busy} value={module} onChange={(event) => { setModule(event.target.value); setOffset(0); setNotice(""); }} className="mt-2 block min-h-11 w-full rounded-lg border border-slate-300 bg-white px-3 sm:max-w-xs"><option value="leads">Leads</option><option value="customers">Customers</option><option value="quotations">Quotations</option></select></label>
    {notice && <p role="status" className="mt-3 rounded-lg bg-slate-50 p-3 text-xs leading-5">{notice}</p>}
    {!current ? <p role="status" className="py-5 text-sm">Loading assignments...</p> : current.error ? <div className="py-4"><p role="alert" className="text-sm text-rose-900">{current.error}</p><Button variant="secondary" className="mt-3" onClick={() => setRevision((value) => value + 1)}>Retry</Button></div> : <>
      <div className="mt-4 min-w-0 divide-y divide-slate-100"><div aria-hidden="true" className="hidden grid-cols-[minmax(0,1fr)_minmax(0,240px)] gap-3 py-2 text-[11px] font-semibold text-slate-600 xl:grid"><span>Record</span><span>Assigned account</span></div>{current.data.records.length === 0 && <p className="py-4 text-sm text-slate-700">No records to assign.</p>}{current.data.records.map((record) => <div key={record.id} className="grid min-w-0 grid-cols-1 items-center gap-3 py-3 xl:grid-cols-[minmax(0,1fr)_minmax(0,240px)]"><p className="min-w-0 break-words text-sm font-semibold leading-6">{record.label}</p><label className="block w-full min-w-0 text-xs"><span className="mb-1.5 block text-[11px] font-medium text-slate-600 xl:sr-only xl:mb-0">Assigned account<span className="sr-only"> for {record.label}</span></span><select disabled={busy} value={record.assigneeUserId || ""} onChange={(event) => save(record, event.target.value)} className="min-h-11 w-full min-w-0 max-w-full rounded-lg border border-slate-300 bg-white px-3 text-sm"><option value="">Unassigned — Admin only</option>{record.assigneeUserId && !current.data.users.some((user) => user.id === record.assigneeUserId) && <option value={record.assigneeUserId}>Inactive account</option>}{current.data.users.map((user) => <option key={user.id} value={user.id}>{user.name} ({user.role})</option>)}</select></label></div>)}</div>
      <div className="mt-4 flex items-center justify-between gap-3"><Button variant="secondary" disabled={busy || offset === 0} onClick={() => setOffset((value) => Math.max(0, value - 25))}>Previous</Button><span className="text-xs text-slate-700">Page {offset / 25 + 1}</span><Button variant="secondary" disabled={busy || !current.data.hasMore} onClick={() => setOffset((value) => value + 25)}>Next</Button></div>
    </>}
  </section>;
}
