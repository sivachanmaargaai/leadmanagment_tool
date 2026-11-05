import { useEffect, useId, useRef } from "react";
import { X } from "lucide-react";
import { IconButton } from "./ui";

export default function Modal({ title, onClose, children }) {
  const ref = useRef(null);
  const titleId = useId();
  useEffect(() => { if (!ref.current.open) ref.current.showModal(); }, []);
  return <dialog ref={ref} aria-labelledby={titleId}
    className="m-auto max-h-[94dvh] w-[calc(100%-1rem)] max-w-2xl overflow-y-auto rounded-2xl border border-slate-200 bg-white p-0 text-slate-950 shadow-2xl backdrop:bg-slate-950/40 backdrop:backdrop-blur-sm"
    onCancel={(event) => { event.preventDefault(); onClose(); }}
    onClick={(event) => { if (event.target === event.currentTarget) onClose(); }}>
    <div>
      <header className="flex items-center justify-between gap-4 border-b border-slate-200 px-4 py-3">
        <h2 id={titleId} className="min-w-0 break-words text-base font-bold">{title}</h2>
        <IconButton aria-label="Close dialog" onClick={onClose}><X size={20} /></IconButton>
      </header>
      {children}
    </div>
  </dialog>;
}
