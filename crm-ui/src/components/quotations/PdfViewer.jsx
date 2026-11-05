import { useEffect, useState } from "react";
import { Download } from "lucide-react";
import { Button } from "../ui";
import QuoteDialog from "./QuoteDialog";
import { getQuotationPdf } from "../../services/quotationsApi";
import { downloadPdf } from "../../lib/quotationPdf";

export default function PdfViewer({ quotation, onClose }) {
  const [versionIndex, setVersionIndex] = useState(quotation.versions.length - 1);
  const [pdf, setPdf] = useState(null);
  const [error, setError] = useState("");
  const [retry, setRetry] = useState(0);
  const [downloading, setDownloading] = useState(false);
  const version = quotation.versions[versionIndex];
  const currentPdf = pdf?.version === version?.id && pdf?.retry === retry ? pdf : null;
  const url = currentPdf?.url || "";
  const message = error || currentPdf?.error || (!version ? "No PDF revision available." : "");

  useEffect(() => {
    let active = true;
    let objectUrl;
    if (!version) return;
    getQuotationPdf(version).then((blob) => {
      if (active) { objectUrl = URL.createObjectURL(blob); setPdf({ version: version.id, retry, url: objectUrl }); }
    }).catch((failure) => { if (active) setPdf({ version: version.id, retry, error: failure.message }); });
    return () => { active = false; if (objectUrl) URL.revokeObjectURL(objectUrl); };
  }, [version, retry]);

  async function download() {
    setDownloading(true);
    try { await downloadPdf(version); } catch (failure) { setError(failure.message); }
    finally { setDownloading(false); }
  }

  return <QuoteDialog title={`${quotation.number} · ${quotation.customer}`} onClose={onClose}>
    <div className="flex flex-wrap items-center justify-between gap-3 p-4">
      <label className="flex items-center gap-2 text-xs font-semibold">Version
        <select value={versionIndex} onChange={(event) => { setError(""); setVersionIndex(Number(event.target.value)); }} className="max-w-48 rounded-lg border border-slate-300 bg-white p-2 text-slate-950">
          {quotation.versions.map((entry, index) => <option key={entry.id} value={index}>Revision {entry.revision}{index === quotation.versions.length - 1 ? " - Latest" : ""}</option>)}
        </select>
      </label>
      <Button variant="secondary" disabled={!version || downloading} onClick={download}><Download size={16} />{downloading ? "Downloading..." : "Download PDF"}</Button>
    </div>
    {version && <p className="break-words px-4 pb-3 text-xs text-slate-700">{version.name} · {new Date(version.uploadedAt).toLocaleString("en-IN", { timeZone: "Asia/Kolkata" })}</p>}
    {message ? <div role="alert" className="space-y-3 p-4 text-sm text-rose-900"><p>{message}</p><Button variant="secondary" onClick={() => { setError(""); setRetry((value) => value + 1); }}>Retry</Button></div> : !url ? <p role="status" className="p-6 text-sm text-slate-700">Loading PDF...</p> :
      <object key={url} data={url} type="application/pdf" aria-label={`PDF preview for ${quotation.number}`} className="block h-[65dvh] w-full border-t border-slate-200 bg-slate-100">
        <div className="space-y-3 p-6 text-center text-sm text-slate-800"><p>Preview unavailable in this browser.</p><Button onClick={download}>Download PDF</Button></div>
      </object>}
  </QuoteDialog>;
}
