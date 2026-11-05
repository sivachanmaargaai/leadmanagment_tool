import { Button } from "./ui";
export default function Pagination({ pagination }) {
  return <div className="flex flex-wrap items-center justify-between gap-2 border-t border-slate-100 p-3 text-xs text-slate-700"><span>{pagination.loading ? "Loading records..." : `${pagination.total} records · Page ${pagination.page} / ${pagination.pages}`}</span><div className="flex gap-2"><Button variant="secondary" disabled={pagination.loading || pagination.page <= 1} onClick={() => pagination.setPage(pagination.page - 1)}>Previous</Button><Button variant="secondary" disabled={pagination.loading || pagination.page >= pagination.pages} onClick={() => pagination.setPage(pagination.page + 1)}>Next</Button></div></div>;
}
