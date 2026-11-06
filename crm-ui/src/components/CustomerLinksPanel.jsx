import { useState } from "react";
import Modal from "./Modal";
import RecordPicker from "./RecordPicker";
import Pagination from "./Pagination";
import { Button } from "./ui";
import useServerPage from "../hooks/useServerPage";
import { getLeadsPage } from "../services/leadsApi";
import { getQuotationsPage } from "../services/quotationsApi";
import { apiRequest } from "../services/apiClient";

export default function CustomerLinksPanel({ onClose, onChanged }) {
  const [module, setModule] = useState("leads");
  const [query, setQuery] = useState("");
  const [selected, setSelected] = useState(null);
  const [profile, setProfile] = useState(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [unlinked, setUnlinked] = useState(true);
  const pagination = useServerPage(module === "leads" ? getLeadsPage : getQuotationsPage, { q: query, unlinked, ...(module === "quotations" ? { summary: true } : {}) });
  async function save(customerId) {
    if (busy) return;
    setBusy(true); setError("");
    try {
      await apiRequest(`/api/customer-links/${module}/${encodeURIComponent(selected.id)}`, { method: "PUT", body: JSON.stringify({ customerId, expectedVersion: selected.version }) });
      setSelected(null); setProfile(null); pagination.refresh(); onChanged?.();
    } catch (failure) { setError(failure.message); }
    finally { setBusy(false); }
  }
  return <Modal title="Link existing customer records" onClose={busy ? () => {} : onClose}><div className="space-y-4 p-4 sm:p-5">
    <p className="text-xs leading-6 text-slate-700">Choose the correct profile explicitly. Names can be identical. Linking keeps original quotation PDFs and historical names unchanged. Archived quotation links can be corrected through the administrator API.</p>
    <div className="flex flex-wrap gap-3">
      <select aria-label="Customer link module" value={module} onChange={(event) => { setModule(event.target.value); setSelected(null); setProfile(null); }} className="rounded-lg border border-slate-300 p-2 text-xs"><option value="leads">Leads</option><option value="quotations">Quotations</option></select>
      <input aria-label="Search records to link" value={query} maxLength={120} onChange={(event) => setQuery(event.target.value)} placeholder="Search records" className="min-w-0 flex-1 rounded-lg border border-slate-300 p-2 text-xs" />
      <label className="flex items-center gap-2 text-xs"><input type="checkbox" checked={unlinked} onChange={(event) => setUnlinked(event.target.checked)} />Unlinked only</label>
    </div>
    {(error || pagination.error) && <p role="alert" className="text-xs text-rose-800">{error || pagination.error}</p>}
    {pagination.rows.map((row) => <button key={row.id} type="button" disabled={busy} className={`block w-full rounded-lg border p-3 text-left text-xs ${selected?.id === row.id ? "border-teal-700 bg-teal-50" : "border-slate-200"}`} onClick={() => { setSelected(row); setProfile(null); setError(""); }}><strong>{row.customer}</strong> · {row.number || row.description?.slice(0, 60)}<span className="mt-1 block text-slate-600">{row.customerId ? `Linked: ${row.customerId}` : "Unlinked"}</span></button>)}
    <Pagination pagination={pagination} />
    {selected && <div className="space-y-3 rounded-xl border border-teal-200 p-3"><p className="text-xs font-semibold">Selected: {selected.customer}</p><RecordPicker value={profile?.id} name={profile?.name} disabled={busy} onChange={setProfile} /><div className="flex flex-wrap gap-2"><Button disabled={busy || !profile} onClick={() => save(profile.id)}>Confirm link</Button>{selected.customerId && <Button disabled={busy} variant="secondary" onClick={() => save(null)}>Remove link</Button>}</div></div>}
  </div></Modal>;
}
