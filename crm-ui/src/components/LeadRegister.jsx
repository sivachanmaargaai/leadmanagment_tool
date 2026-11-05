import { useEffect, useState } from "react";
import LeadTable from "./LeadTable";
import { Button } from "./ui";
import useServerPage from "../hooks/useServerPage";
import { getLeadsPage } from "../services/leadsApi";

export default function LeadRegister({ division, revision, onUpdateLead, onDeleteLead }) {
  const [search, setSearch] = useState("");
  const [query, setQuery] = useState("");
  useEffect(() => { const timer = setTimeout(() => setQuery(search.trim()), 300); return () => clearTimeout(timer); }, [search]);
  const pagination = useServerPage(getLeadsPage, { division, q: query }, revision);
  return <div className="space-y-3"><div className="flex flex-wrap items-center justify-between gap-2 text-xs text-slate-700"><span>{pagination.loading ? "Loading leads..." : `${pagination.total} matching leads`}</span><Button variant="secondary" disabled={pagination.loading} onClick={pagination.refresh}>Reload leads</Button></div>
    {pagination.error && <p role="alert" className="rounded-lg bg-rose-50 p-3 text-sm text-rose-900">{pagination.error}</p>}
    <LeadTable leads={pagination.rows} onUpdateLead={onUpdateLead} onDeleteLead={onDeleteLead} remote={{ pagination, search, setSearch }} />
  </div>;
}
