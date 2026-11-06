import { useEffect, useRef, useState } from "react";
import { ShieldCheck, Users } from "lucide-react";
import { Button, Card, CardHeading } from "../ui";
import { getRolePermissions, saveStaffPermissions } from "../../services/permissionsApi";

export default function RolePermissions() {
  const [saved, setSaved] = useState(null);
  const [quotations, setQuotations] = useState(false);
  const [attempt, setAttempt] = useState(0);
  const [busy, setBusy] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const lock = useRef(false);
  useEffect(() => {
    const controller = new AbortController();
    const timer = setTimeout(() => {
      getRolePermissions(controller.signal).then((data) => {
        if (!controller.signal.aborted) { setSaved(data); setQuotations(data.roles.Staff.quotations); setError(""); }
      }).catch((failure) => { if (!controller.signal.aborted) setError(failure.message); })
        .finally(() => { if (!controller.signal.aborted) setLoading(false); });
    }, 0);
    return () => { clearTimeout(timer); controller.abort(); };
  }, [attempt]);
  async function save(event) {
    event.preventDefault();
    if (lock.current || !saved || loading) return;
    lock.current = true; setBusy(true); setError(""); setNotice("");
    try {
      const data = await saveStaffPermissions(quotations, saved.version);
      setSaved(data); setQuotations(data.roles.Staff.quotations);
      setNotice("Staff permissions saved. All staff must sign in again to use the updated access.");
      window.dispatchEvent(new Event("crm:users-updated"));
    } catch (failure) { setError(failure.message); }
    finally { lock.current = false; setBusy(false); }
  }
  return <Card>
    <CardHeading title="Roles & permissions" description="Choose which modules the Staff role can use. Changes apply to all current and future staff." />
    <form onSubmit={save} className="space-y-4 px-4 pb-4 sm:px-5 sm:pb-5">
      <section className="rounded-xl border border-slate-200 bg-slate-50 p-4">
        <h3 className="flex items-center gap-2 text-sm font-bold text-slate-950"><ShieldCheck size={18} />Admin</h3>
        <label className="mt-3 flex items-center gap-3 text-sm font-semibold text-slate-700"><input type="checkbox" checked disabled className="size-4 accent-teal-800" />Full access</label>
        <p className="mt-2 text-xs leading-5 text-slate-600">Admin access is always enabled. Account and role management still follow the Owner rules.</p>
      </section>
      <section className="rounded-xl border border-teal-200 bg-white p-4">
        <h3 className="flex items-center gap-2 text-sm font-bold text-slate-950"><Users size={18} />Staff</h3>
        {!saved && !error && <p role="status" className="mt-3 text-xs text-slate-600">Loading role permissions...</p>}
        <label className="mt-4 flex items-start gap-3"><input type="checkbox" checked={quotations} disabled={!saved || busy || loading} onChange={(event) => { setQuotations(event.target.checked); setNotice(""); }} className="mt-0.5 size-4 shrink-0 accent-teal-800" /><span className="min-w-0"><strong className="block text-sm text-slate-950">Quotations</strong><span className="mt-1 block text-xs leading-5 text-slate-600">Tick to show and allow the quotation module, PDF downloads and quotation reports for all Staff. Uncheck to hide and block access.</span></span></label>
        <p className="mt-4 rounded-lg bg-teal-50 p-3 text-xs leading-5 text-teal-950">Staff still see only their assigned records. This permission applies to the whole Staff role; individual overrides are not used.</p>
      </section>
      {error && <p role="alert" className="rounded-lg bg-rose-50 p-3 text-xs text-rose-900">{error} Reload permissions before retrying a conflict.</p>}
      {notice && <p role="status" className="rounded-lg bg-teal-50 p-3 text-xs text-teal-950">{notice}</p>}
      <div className="flex flex-wrap items-center justify-between gap-3 border-t border-slate-100 pt-4"><p className="text-xs text-slate-600">Access changes sign all Staff out; Admin sessions stay active.</p><div className="flex flex-wrap gap-2"><Button variant="secondary" disabled={busy || loading} onClick={() => { setLoading(true); setAttempt((value) => value + 1); setNotice(""); }}>Reload permissions</Button><Button type="submit" disabled={!saved || busy || loading || quotations === saved.roles.Staff.quotations}>{busy ? "Saving..." : "Save permissions"}</Button></div></div>
    </form>
  </Card>;
}
