import { useState } from "react";
import { Button, EmptyState } from "../ui";
import { runtimeSettings } from "../../lib/runtimeSettings";

export default function ReportTable({ rows, columns, onFilteredRows }) {
  const [search, setSearch] = useState("");
  const [page, setPage] = useState(1);
  const filtered = rows.filter((row) => JSON.stringify(row).toLowerCase().includes(search.trim().toLowerCase()));
  const size = runtimeSettings().workspace.rowsPerPage;
  const pages = Math.max(1, Math.ceil(filtered.length / size));
  const current = Math.min(page, pages);
  const visible = filtered.slice((current - 1) * size, current * size);
  function searchRows(event) {
    const value = event.target.value;
    setSearch(value); setPage(1);
    onFilteredRows?.(rows.filter((row) => JSON.stringify(row).toLowerCase().includes(value.trim().toLowerCase())));
  }
  return <div>
    <div className="border-y border-slate-100 px-4 py-3"><input aria-label="Search report records" placeholder="Search report records..." value={search} onChange={searchRows} className="min-h-10 w-full rounded-lg border border-slate-300 px-3 text-sm text-slate-950 outline-none focus:border-teal-600 sm:max-w-sm" /></div>
    {!filtered.length ? <EmptyState title="No records in this report" description="Adjust dates, division or status. Enable test data to see the sample records." /> : <>
      <div className="grid gap-3 p-3 sm:grid-cols-2 lg:hidden">{visible.map((row, index) => <article key={row.id || index} className="min-w-0 rounded-xl border border-slate-200 p-3 shadow-sm"><dl className="grid grid-cols-2 gap-3">{columns.map((column) => <div key={column.key} className="min-w-0"><dt className="text-[10px] font-semibold text-slate-600">{column.label}</dt><dd className="mt-1 break-words text-xs font-medium text-slate-950">{column.render ? column.render(row) : row[column.key]}</dd></div>)}</dl></article>)}</div>
      <div className="hidden overflow-x-auto lg:block"><table className="w-full text-left text-xs"><thead className="bg-slate-50 text-[10px] uppercase text-slate-700"><tr>{columns.map((column) => <th key={column.key} className="whitespace-nowrap px-4 py-3">{column.label}</th>)}</tr></thead><tbody className="divide-y divide-slate-100">{visible.map((row, index) => <tr key={row.id || index} className="text-slate-900 transition-colors hover:bg-teal-50/40">{columns.map((column) => <td key={column.key} className="max-w-72 break-words px-4 py-3">{column.render ? column.render(row) : row[column.key]}</td>)}</tr>)}</tbody></table></div>
    </>}
    <div className="flex flex-wrap items-center justify-between gap-2 border-t border-slate-100 p-3 text-xs text-slate-700"><span>{filtered.length} records · Page {current} / {pages}</span><div className="flex gap-2"><Button variant="secondary" disabled={current <= 1} onClick={() => setPage(current - 1)}>Previous</Button><Button variant="secondary" disabled={current >= pages} onClick={() => setPage(current + 1)}>Next</Button></div></div>
  </div>;
}
