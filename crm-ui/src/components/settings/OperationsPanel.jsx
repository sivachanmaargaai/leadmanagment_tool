import { useEffect, useState } from "react";
import { getOperationsStatus } from "../../services/operationsApi";
import { Button } from "../ui";

export default function OperationsPanel() {
  const [attempt, setAttempt] = useState(0);
  const [result, setResult] = useState(null);
  const current = result?.attempt === attempt ? result : null;
  useEffect(() => {
    const controller = new AbortController();
    getOperationsStatus(controller.signal).then((data) => { if (!controller.signal.aborted) setResult({ attempt, data }); })
      .catch((error) => { if (!controller.signal.aborted) setResult({ attempt, error: error.message }); });
    return () => controller.abort();
  }, [attempt]);
  const data = current?.data;
  return <section className="mt-4 rounded-xl border border-slate-200 bg-white p-4 text-slate-950 shadow-sm sm:p-5">
    <div className="flex flex-wrap items-center justify-between gap-3"><h2 className="text-lg font-bold">System health & backups</h2><Button variant="secondary" disabled={!current} onClick={() => setAttempt((value) => value + 1)}>Refresh status</Button></div>
    {!current ? <p role="status" className="mt-3 text-sm text-slate-700">Checking system status...</p> : current.error ? <p role="alert" className="mt-3 rounded-lg bg-rose-50 p-3 text-sm text-rose-900">{current.error}</p> : <>
      <p role="status" className={`mt-3 rounded-lg p-3 text-sm font-semibold ${data.status === "ok" ? "bg-teal-50 text-teal-950" : "bg-amber-50 text-amber-950"}`}>{data.status === "ok" ? "Local checks passed" : "Some checks need attention"}</p>
      <dl className="mt-4 grid gap-3 text-xs sm:grid-cols-2 lg:grid-cols-3">{[
        ["Database", data.database.reachable && data.database.schemaCurrent ? "Ready" : "Not ready"],
        ["Latest local backup", data.backup.createdAt ? new Date(data.backup.createdAt).toLocaleString("en-IN", { timeZone: "Asia/Kolkata" }) + " IST" : "Not configured"],
        ["Restore drill", data.backup.restoreVerifiedAt ? "Verified" : "Not verified"],
        ["Requests since worker start", data.metrics.requests], ["Server errors (recent)", data.metrics.recentServerErrors], ["Slow requests", data.metrics.slowRequests],
      ].map(([label, value]) => <div key={label} className="rounded-lg border border-slate-200 p-3 shadow-sm"><dt className="text-slate-700">{label}</dt><dd className="mt-2 break-words font-semibold">{value}</dd></div>)}</dl>
      {data.issues.length > 0 && <p className="mt-3 text-xs leading-6 text-amber-950">Checks: {data.issues.map((issue) => issue.replaceAll("-", " ")).join(", ")}.</p>}
      <p className="mt-3 text-xs leading-6 text-slate-700">Automatic backup schedule and offsite copies are not configured. Metrics apply to the current server worker. This panel only checks status.</p>
    </>}
  </section>;
}
