import { useEffect, useState } from "react";
import { apiRequest } from "../services/apiClient";

export default function useWorkspaceData(kind, division, revision = 0, assignedTo = "", notifications = {}) {
  const [result, setResult] = useState(null);
  const [tick, setTick] = useState(0);
  const query = new URLSearchParams();
  if (division && division !== "All divisions") query.set("division", division);
  if (assignedTo && assignedTo !== "All staff") query.set("assignedTo", assignedTo);
  if (kind === "overview") for (const key of ["leadPriority", "followUp", "overdue", "quotationExpiry"]) if (notifications[key] !== undefined) query.set(key, String(notifications[key]));
  const path = `/api/workspace/${kind}?${query}`;
  const key = `${path}:${revision}:${tick}`;
  useEffect(() => {
    const timer = setInterval(() => setTick((value) => value + 1), 60000);
    return () => clearInterval(timer);
  }, []);
  useEffect(() => {
    const controller = new AbortController();
    const timer = setTimeout(() => { apiRequest(path, { signal: controller.signal }).then((data) => {
      if (!controller.signal.aborted) setResult({ key, path, data });
    }).catch((error) => {
      if (!controller.signal.aborted) setResult({ key, path, error: error.message });
    }); }, 0);
    return () => { clearTimeout(timer); controller.abort(); };
  }, [path, key]);
  return { data: result?.path === path ? result.data : null, error: result?.path === path ? result.error || "" : "", loading: result?.key !== key };
}
