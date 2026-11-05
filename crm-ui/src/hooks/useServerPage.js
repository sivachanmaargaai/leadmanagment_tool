import { useEffect, useState } from "react";
import { runtimeSettings } from "../lib/runtimeSettings";

export default function useServerPage(loader, filters, revision = "") {
  const size = runtimeSettings().workspace.rowsPerPage;
  const filterKey = JSON.stringify(filters);
  const [cursor, setCursor] = useState({ key: "", page: 1 });
  const [reload, setReload] = useState(0);
  const [result, setResult] = useState(null);
  const cursorKey = `${filterKey}:${size}`;
  const page = cursor.key === cursorKey ? cursor.page : 1;
  const key = `${cursorKey}:${page}:${revision}:${reload}`;
  const current = result?.key === key ? result : null;
  useEffect(() => {
    const controller = new AbortController();
    loader({ ...JSON.parse(filterKey), page, pageSize: size, signal: controller.signal }).then((data) => {
      if (controller.signal.aborted) return;
      if (data.page > data.pages) setCursor({ key: cursorKey, page: data.pages });
      else setResult({ key, data });
    }).catch((error) => { if (!controller.signal.aborted) setResult({ key, error: error.message }); });
    return () => controller.abort();
  }, [loader, filterKey, page, size, key, cursorKey]);
  return { rows: current?.data?.items || [], page, pages: current?.data?.pages || 1, total: current?.data?.total || 0,
    loading: !current, error: current?.error || "", refresh: () => setReload((value) => value + 1),
    setPage: (value) => setCursor({ key: cursorKey, page: value }) };
}
