import { useEffect, useRef } from "react";
export default function useNotificationSound(alerts, enabled) {
  const audio = useRef(null);
  const seen = useRef(null);
  useEffect(() => {
    if (!enabled) return;
    const arm = () => {
      const Audio = window.AudioContext || window.webkitAudioContext;
      if (!Audio) return;
      try { if (!audio.current) audio.current = new Audio(); audio.current.resume().catch(() => {}); } catch { /* Browser audio may be unavailable. */ }
    };
    window.addEventListener("pointerdown", arm);
    window.addEventListener("keydown", arm);
    return () => { window.removeEventListener("pointerdown", arm); window.removeEventListener("keydown", arm); const context = audio.current; audio.current = null; context?.close().catch(() => {}); };
  }, [enabled]);
  useEffect(() => {
    const ids = new Set(alerts.map((item) => item.id));
    const added = seen.current && [...ids].some((id) => !seen.current.has(id));
    seen.current = ids;
    const context = audio.current;
    if (!enabled || !added || context?.state !== "running") return;
    const tone = context.createOscillator();
    const volume = context.createGain();
    tone.frequency.value = 660; volume.gain.value = 0.04;
    tone.connect(volume); volume.connect(context.destination); tone.start(); tone.stop(context.currentTime + 0.12);
    tone.onended = () => { tone.disconnect(); volume.disconnect(); };
  }, [alerts, enabled]);
}
