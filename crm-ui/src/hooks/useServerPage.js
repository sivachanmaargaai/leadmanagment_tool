import { useEffect, useState } from "react";
import { runtimeSettings } from "../lib/runtimeSettings";

export default function useServerPage(loader, filters, revision = "", { enabled = true } = {}) {
  const size = Math.min(100, Math.max(1, filters.pageSize || runtimeSettings().workspace.rowsPerPage));
  const filterKey = JSON.stringify(filters);
  const [cursor, setCursor] = useState({ key: "", page: 1 });
  const [reload, setReload] = useState(0);
  const [result, setResult] = useState(null);
  const cursorKey = `${filterKey}:${size}`;
  const page = cursor.key === cursorKey ? cursor.page : 1;
  const key = `${cursorKey}:${page}:${revision}:${reload}`;
  const current = result?.key === key ? result : null;
  useEffect(() => {
    if (!enabled) return;
    const controller = new AbortController();
    const timer = setTimeout(() => { loader({ ...JSON.parse(filterKey), page, pageSize: size, signal: controller.signal }).then((data) => {
      if (controller.signal.aborted) return;
      if (data.page > data.pages) setCursor({ key: cursorKey, page: data.pages });
      else setResult({ key, data });
    }).catch((error) => { if (!controller.signal.aborted) setResult({ key, error: error.message }); }); }, JSON.parse(filterKey).q ? 300 : 0);
    return () => { clearTimeout(timer); controller.abort(); };
  }, [loader, filterKey, page, size, key, cursorKey, enabled]);
  if (!enabled) return { rows: [], page: 1, pages: 1, total: 0, loading: false, error: "", refresh: () => {}, setPage: () => {} };
  return { rows: current?.data?.items || [], page, pages: current?.data?.pages || 1, total: current?.data?.total || 0,
    loading: !current, error: current?.error || "", refresh: () => setReload((value) => value + 1),
    setPage: (value) => setCursor({ key: cursorKey, page: value }) };
}
