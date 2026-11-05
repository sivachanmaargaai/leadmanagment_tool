import { useEffect, useState } from "react";
import { getQuotations } from "../services/quotationsApi";
export default function useQuotationAlerts(enabled) {
  const [data, setData] = useState({ quotes: [], error: "" });
  useEffect(() => {
    if (!enabled) return;
    let active = true;
    const refresh = () => getQuotations().then((quotes) => { if (active) setData({ quotes, error: "" }); }).catch(() => { if (active) setData((old) => ({ ...old, error: "Quotation alerts could not be refreshed." })); });
    refresh();
    const timer = setInterval(refresh, 60000);
    return () => { active = false; clearInterval(timer); };
  }, [enabled]);
  return { quotes: data.quotes, error: enabled ? data.error : "" };
}
