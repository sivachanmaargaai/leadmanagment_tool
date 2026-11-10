import { useEffect, useId, useState } from "react";
import { getCustomersPage } from "../services/customersApi";
import { getLeadsPage } from "../services/leadsApi";
import { divisionLabel } from "../data/crm";

// Explicit selection disambiguates identical names. Never downloads the directory.
export default function RecordPicker({ kind = "customer", value, name = "", onChange, disabled = false }) {
  const [query, setQuery] = useState("");
  const [open, setOpen] = useState(false);
  const [result, setResult] = useState(null);
  const id = useId();
  useEffect(() => {
    if (!open) return;
    const controller = new AbortController();
    const timer = setTimeout(() => {
      const loader = kind === "customer" ? getCustomersPage : getLeadsPage;
      loader({ q: query, pageSize: 20, signal: controller.signal }).then((data) => {
        if (!controller.signal.aborted) setResult({ query, data });
      }).catch((error) => { if (!controller.signal.aborted) setResult({ query, error: error.message }); });
    }, 250);
    return () => { clearTimeout(timer); controller.abort(); };
  }, [kind, open, query]);
  const current = result?.query === query ? result : null;
  return <div className="min-w-0 space-y-2">
    {value && <p className="break-words text-xs text-teal-900">Linked: {name} <span className="text-slate-600">· {value.slice(0, 8)}</span></p>}
    {!disabled && <button type="button" className="text-xs font-semibold text-teal-800 underline" onClick={() => setOpen(!open)}>{open ? "Close search" : `Select ${kind} profile`}</button>}
    {open && !disabled && <div className="space-y-2 rounded-lg border border-teal-200 bg-teal-50/40 p-3">
      <label htmlFor={id} className="block text-xs font-semibold text-slate-800">Search {kind}s</label>
      <input id={id} value={query} maxLength={120} onChange={(event) => setQuery(event.target.value)} className="w-full min-w-0 rounded-lg border border-slate-300 bg-white p-2 text-sm text-slate-950" placeholder="Type a name…" />
      {current?.error && <p role="alert" className="text-xs text-rose-800">{current.error}</p>}
      {!current && <p className="text-xs text-slate-600">Searching…</p>}
      <div className="max-h-48 overflow-y-auto">{current?.data?.items.map((item) => <button key={item.id} type="button" className="block w-full break-words rounded-md p-2 text-left text-xs text-slate-950 hover:bg-teal-100 focus-visible:outline-2 focus-visible:outline-teal-700" onClick={() => { onChange(item); setOpen(false); }}>
        <strong>{kind === "customer" ? item.name : item.customer}</strong><span className="ml-2 text-slate-600">{kind === "customer" ? item.contacts?.[0]?.email || item.city : `${divisionLabel(item.division)} · ${item.description?.slice(0, 60)}`}</span><small className="block text-slate-500">ID: {item.id}</small>
      </button>)}</div>
      {current?.data && <p className="text-[11px] text-slate-600">Showing up to 20 of {current.data.total}. Refine the search to find another record.</p>}
    </div>}
  </div>;
}
