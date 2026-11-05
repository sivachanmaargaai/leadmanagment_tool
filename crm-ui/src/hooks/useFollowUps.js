import { useCallback, useEffect, useRef, useState } from "react";
import { createFollowUp, getFollowUps, updateFollowUp } from "../services/followUpsApi.js";

export default function useFollowUps() {
  const [followUps, setFollowUps] = useState([]);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [now, setNow] = useState(Date.now);
  const generation = useRef(0);
  const saving = useRef(false);
  const mounted = useRef(false);

  const refresh = useCallback(async () => {
    if (saving.current) return;
    const request = ++generation.current;
    try {
      const records = await getFollowUps();
      if (mounted.current && request === generation.current) { setFollowUps(records); setError(""); }
    } catch (loadError) {
      if (mounted.current && request === generation.current) setError(loadError.message);
    } finally {
      if (mounted.current && request === generation.current) setLoading(false);
    }
  }, []);

  useEffect(() => {
    mounted.current = true;
    const requestGeneration = generation;
    queueMicrotask(() => { if (mounted.current) refresh(); });
    const timer = setInterval(() => { setNow(Date.now()); refresh(); }, 30000);
    return () => { mounted.current = false; ++requestGeneration.current; clearInterval(timer); };
  }, [refresh]);

  async function saveFollowUps(record, next) {
    if (saving.current) throw new Error("A follow-up is already being saved. Please wait.");
    saving.current = true;
    ++generation.current;
    try {
      const result = record.version ? await updateFollowUp(record, next) : { record: await createFollowUp(record) };
      ++generation.current;
      setFollowUps((current) => {
        const exists = current.some((item) => item.id === result.record.id);
        const updated = exists ? current.map((item) => item.id === result.record.id ? result.record : item) : [result.record, ...current];
        return result.nextFollowUp ? [result.nextFollowUp, ...updated] : updated;
      });
      setError("");
      setNow(Date.now());
    } finally {
      saving.current = false;
    }
  }

  return { followUps, saveFollowUps, error, loading, refresh, now };
}
