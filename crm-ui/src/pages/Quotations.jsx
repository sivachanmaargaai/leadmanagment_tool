import { useSettings } from "../context/SettingsContext";
import { displayDate } from "../lib/runtimeSettings";
import useServerPage from "../hooks/useServerPage";
import useWorkspaceData from "../hooks/useWorkspaceData";
import Pagination from "../components/Pagination";
import { useRef, useState } from "react";
import {
    Plus,
    Upload,
    Eye,
    Download,
    Search,
    FileText,
    Pencil,
    Trash2,
} from "lucide-react";
import { divisionLabel, divisions } from "../data/crm";
import {
    Button,
    Card,
    CardHeading,
    EmptyState,
    IconButton,
} from "../components/ui";
import PdfViewer from "../components/quotations/PdfViewer";
import QuoteForm from "../components/quotations/QuoteForm";
import { getQuotationsPage, getQuotationById, createQuotation, updateQuotation, uploadQuotationRevision, deleteQuotation } from "../services/quotationsApi";
import {
    billingTypes,
    quoteStatuses,
    money,
    effectiveStatus,
    downloadPdf,
    validatePdf,
} from "../lib/quotationPdf";

const selectClass =
    "rounded-lg border border-slate-300 bg-white px-3 py-2 text-xs text-slate-900 outline-none focus:border-teal-600 focus:ring-2 focus:ring-teal-100";

export default function Quotations({ onChanged }) {
    const { user: accessUser } = useSettings();
    const [error, setError] = useState("");
    const [notice, setNotice] = useState("");
    const [mode, setMode] = useState(null);
    const [preview, setPreview] = useState(null);
    const [search, setSearch] = useState("");
    const [division, setDivision] = useState("All divisions");
    const [status, setStatus] = useState("All statuses");
    const [busyId, setBusyId] = useState(null);

    const actionLock = useRef(false);
    const [editing, setEditing] = useState(null);
    const [reload, setReload] = useState(0);
    const revisionInput = useRef(null);
    const revisionTarget = useRef(null);

    const pagination = useServerPage(getQuotationsPage, { q: search, division, status, summary: true }, reload);
    const { rows: pageRows, loading } = pagination;
    const metrics = useWorkspaceData("metrics", division, reload);
    function replaceQuotation() {
        setReload((value) => value + 1); onChanged?.();
    }

    async function addQuotation(draft, file) {
        const record = editing
            ? file ? await uploadQuotationRevision(editing, file, draft) : await updateQuotation(editing, { document: draft })
            : await createQuotation(draft, file);
        replaceQuotation(record);
        setMode(null);
        setEditing(null);
        setNotice(editing ? "Revision saved. Previous PDFs retained; status reset to Draft." : "Quotation and PDF saved to the server.");
    }

    async function action(quote, operation, message) {
        if (actionLock.current) return;
        actionLock.current = true;
        setBusyId(quote.id); setError(""); setNotice("");
        try { const record = await operation(); if (record) replaceQuotation(record); setNotice(message); }
        catch (failure) { setError(failure.message); }
        finally { actionLock.current = false; setBusyId(null); }
    }

    function changeStatus(quote, status) {
        return action(quote, () => updateQuotation(quote, { status }), "Status updated. The retained PDF is unchanged.");
    }

    async function download(version) {
        try { await downloadPdf(version); } catch (failure) { setError(failure.message); }
    }

    async function edit(quote) {
        await action(quote, async () => { const full = await getQuotationById(quote.id); setEditing(full); setMode(full.source === "Uploaded" ? "revision" : "edit"); }, "");
    }
    async function view(quote) {
        await action(quote, async () => { setPreview(await getQuotationById(quote.id)); }, "");
    }

    function archive(quote) {
        if (!window.confirm("Archive " + quote.number + "? Its PDF history will be retained on the server.")) return;
        return action(quote, async () => {
            await deleteQuotation(quote);
            replaceQuotation();
        }, "Quotation archived. PDF history retained.");
    }

    async function uploadRevision(event) {
        const file = event.target.files?.[0];
        const quote = revisionTarget.current;
        event.target.value = "";
        revisionTarget.current = null;
        if (!file || !quote) return;
        return action(quote, async () => { await validatePdf(file); return uploadQuotationRevision(quote, file); },
            "Revision saved; old PDFs retained and status reset to Draft. Amount and dates are unchanged. Use Edit to revise details.");
    }

    return (
        <div className="space-y-4">
            <div className="flex flex-wrap items-center justify-between gap-4">
                <p className="max-w-xl text-xs leading-6 text-slate-700">
                    Create quotations or keep existing PDFs in one place.
                    PDFs and revision history are stored on the server.
                </p>

                <div className="flex flex-wrap gap-3">
                    <Button
                        variant="secondary"
                        disabled={loading || Boolean(error) || busyId !== null}
                        onClick={() => { setEditing(null); setMode("upload"); }}
                    >
                        <Upload size={16} /> Upload PDF
                    </Button>
                    <Button
                        disabled={loading || Boolean(error) || busyId !== null}
                        onClick={() => { setEditing(null); setMode("create"); }}
                    >
                        <Plus size={16} /> Create quotation
                    </Button>
                </div>
            </div>

            <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 xl:grid-cols-5">
                {["Total", "Draft", "Sent", "Accepted", "Expired"].map((label) => (
                    <Card key={label} className="p-4">
                        <p className="text-xs font-semibold text-slate-700">
                            {label === "Total" ? "Total quotations" : label}
                        </p>
                        <strong className="mt-2 block text-2xl font-bold text-slate-950">
                            {metrics.data?.quotations?.[label] ?? "…"}
                        </strong>
                    </Card>
                ))}
            </div>

            {(error || pagination.error || metrics.error) && (
                <p
                    role="alert"
                    className="rounded-xl border border-rose-200 bg-rose-50 p-4 text-sm text-rose-900"
                >
                    {error || pagination.error || metrics.error}
                    <button type="button" disabled={busyId !== null || loading} onClick={() => { setError(""); setReload((value) => value + 1); }} className="ml-3 min-h-10 font-semibold underline">Reload quotations</button>
                </p>
            )}

            {notice && (
                <p
                    role="status"
                    className="rounded-xl border border-teal-200 bg-teal-50 p-4 text-xs leading-6 text-teal-950"
                >
                    {notice}
                </p>
            )}

            <Card>
                <CardHeading
                    title="Quotation register"
                    description="Your documents, statuses and revision history."
                />

                <div className="flex flex-wrap gap-3 border-t border-slate-100 px-5 py-4">
                    <label className="flex min-w-44 flex-1 items-center gap-2 rounded-lg border border-slate-300 px-3 py-2 focus-within:ring-2 focus-within:ring-teal-100">
                        <Search size={16} className="text-slate-700" />
                        <input
                            aria-label="Search quotations"
                            placeholder="Search customer or quotation number..."
                            value={search}
                            onChange={(event) => setSearch(event.target.value)}
                            className="w-full bg-transparent text-xs text-slate-950 outline-none placeholder:text-slate-500"
                        />
                    </label>

                    <select
                        aria-label="Filter by division"
                        value={division}
                        onChange={(event) => setDivision(event.target.value)}
                        className={selectClass}
                    >
                        <option>All divisions</option>
                        {divisions.map((name) => (
                            <option key={name} value={name}>{divisionLabel(name)}</option>
                        ))}
                    </select>

                    <select
                        aria-label="Filter by status"
                        value={status}
                        onChange={(event) => setStatus(event.target.value)}
                        className={selectClass}
                    >
                        <option>All statuses</option>
                        {quoteStatuses.map((name) => (
                            <option key={name}>{name}</option>
                        ))}
                    </select>
                </div>

                {loading ? (
                    <p className="p-10 text-center text-sm text-slate-700">
                        Loading quotations...
                    </p>
                ) : pageRows.length === 0 ? (
                    <EmptyState
                        icon={FileText}
                        title="No quotations found"
                        description="Create a quotation, upload a PDF, or adjust your filters."
                    />
                ) : (
                    <>
                    <div className="grid gap-3 px-3 pb-3 sm:grid-cols-2 lg:hidden">
                        {pageRows.map((quote) => <article key={quote.id} className="min-w-0 rounded-xl border border-slate-200 p-3 shadow-sm shadow-slate-900/5">
                            <div className="flex flex-wrap items-start justify-between gap-2">
                                <div className="min-w-0"><strong className="block break-words text-sm text-slate-950">{quote.customer}</strong><p className="mt-1 break-all text-[11px] font-medium text-teal-800">{quote.number}</p></div>
                                <select aria-label={`Status for ${quote.number}`} value={effectiveStatus(quote)} disabled={busyId !== null} onChange={(event) => changeStatus(quote, event.target.value)} className={selectClass}>{quoteStatuses.map((name) => <option key={name}>{name}</option>)}</select>
                            </div>
                            <dl className="mt-3 space-y-1.5 text-[11px] text-slate-700"><div className="flex justify-between gap-3"><dt>Division</dt><dd className="font-semibold text-slate-900">{divisionLabel(quote.division)}</dd></div><div className="flex justify-between gap-3"><dt>Valid until</dt><dd>{displayDate(quote.validUntil)}</dd></div></dl>
                            <div className="my-3 rounded-lg bg-teal-50 p-2.5">{billingTypes.filter((billing) => quote.totals[billing]).map((billing) => <p key={billing} className="flex flex-wrap justify-between gap-2 text-xs leading-6 text-teal-950"><span>{billing}</span><strong>{money(quote.totals[billing].total, quote.currency)}</strong></p>)}</div>
                            <div className="flex items-center justify-between gap-2 border-t border-slate-100 pt-2"><span className="text-[10px] text-slate-600">{quote.versionCount ?? quote.versions.length} version(s)</span><div className="flex gap-1">
                                <IconButton aria-label={`Edit ${quote.number}`} disabled={busyId !== null} onClick={() => edit(quote)}><Pencil size={17} /></IconButton>
                                {accessUser.role === "Admin" && <IconButton aria-label={`Archive ${quote.number}`} disabled={busyId !== null} onClick={() => archive(quote)}><Trash2 size={17} /></IconButton>}
                                <IconButton aria-label={`View ${quote.number}`} onClick={() => view(quote)}><Eye size={17} /></IconButton>
                                <IconButton aria-label={`Download ${quote.number}`} onClick={() => download(quote.versions.at(-1))}><Download size={17} /></IconButton>
                                <IconButton aria-label={`Upload revision for ${quote.number}`} disabled={busyId !== null} onClick={() => { revisionTarget.current = quote; revisionInput.current.click(); }}><Upload size={17} /></IconButton>
                            </div></div>
                        </article>)}
                    </div>
                    <div className="hidden overflow-x-auto lg:block">
                        <table className="w-full whitespace-nowrap text-left">
                            <thead className="border-y border-slate-200 bg-slate-50 text-[10px] uppercase tracking-wide text-slate-700">
                                <tr>
                                    {[
                                        "Quotation",
                                        "Customer",
                                        "Division",
                                        "Dates",
                                        "Amount",
                                        "Status",
                                        "Actions",
                                    ].map((heading) => (
                                        <th key={heading} className="px-5 py-3">
                                            {heading}
                                        </th>
                                    ))}
                                </tr>
                            </thead>

                            <tbody className="divide-y divide-slate-100">
                                {pageRows.map((quote) => (
                                    <tr
                                        key={quote.id}
                                        className="text-xs text-slate-800 transition-colors hover:bg-teal-50/40"
                                    >
                                        <td className="px-5 py-4">
                                            <strong className="block text-slate-950">
                                                {quote.number}
                                            </strong>
                                            <small className="mt-1 block text-slate-600">
                                                {quote.source} · {quote.versionCount ?? quote.versions.length} version(s)
                                            </small>
                                        </td>

                                        <td className="px-5 py-4 font-medium">
                                            {quote.customer}
                                        </td>

                                        <td className="px-5 py-4">{divisionLabel(quote.division)}</td>

                                        <td className="px-5 py-4">
                                            <span className="block">{displayDate(quote.date)}</span>
                                            <small className="mt-1 block text-slate-600">
                                                Valid: {displayDate(quote.validUntil)}
                                            </small>
                                        </td>

                                        <td className="px-5 py-4">
                                            {billingTypes
                                                .filter((billing) => quote.totals[billing])
                                                .map((billing) => (
                                                    <span key={billing} className="block leading-6">
                                                        {money(quote.totals[billing].total, quote.currency)}
                                                        <small className="ml-1 text-slate-600">
                                                            {billing === "One-time"
                                                                ? "once"
                                                                : billing === "Monthly"
                                                                    ? "/ month"
                                                                    : "/ year"}
                                                        </small>
                                                    </span>
                                                ))}
                                        </td>

                                        <td className="px-5 py-4">
                                            <select
                                                aria-label={`Status for ${quote.number}`}
                                                value={effectiveStatus(quote)}
                                                disabled={busyId !== null}
                                                onChange={(event) =>
                                                    changeStatus(quote, event.target.value)
                                                }
                                                className={selectClass}
                                            >
                                                {quoteStatuses.map((name) => (
                                                    <option key={name}>{name}</option>
                                                ))}
                                            </select>
                                        </td>

                                        <td className="px-5 py-4">
                                            <div className="flex gap-1">
                                                <IconButton aria-label={`Edit ${quote.number}`} title="Edit details and create a revision" disabled={busyId !== null} onClick={() => edit(quote)}><Pencil size={17} /></IconButton>
                                                {accessUser.role === "Admin" && <IconButton aria-label={`Archive ${quote.number}`} title="Archive quotation" disabled={busyId !== null} onClick={() => archive(quote)}><Trash2 size={17} /></IconButton>}
                                                <IconButton
                                                    aria-label={`View ${quote.number}`}
                                                    title="View PDF & history"
                                                    onClick={() => view(quote)}
                                                >
                                                    <Eye size={17} />
                                                </IconButton>

                                                <IconButton
                                                    aria-label={`Download ${quote.number}`}
                                                    title="Download latest PDF"
                                                    onClick={() =>
                                                        download(quote.versions.at(-1))
                                                    }
                                                >
                                                    <Download size={17} />
                                                </IconButton>

                                                <IconButton
                                                    aria-label={`Upload revision for ${quote.number}`}
                                                    title="Upload revision"
                                                    disabled={busyId !== null}
                                                    onClick={() => {
                                                        revisionTarget.current = quote;
                                                        revisionInput.current.click();
                                                    }}
                                                >
                                                    <Upload size={17} />
                                                </IconButton>
                                            </div>
                                        </td>
                                    </tr>
                                ))}
                            </tbody>
                        </table>
                    </div>
                    </>
                )}

                <Pagination pagination={pagination} />
                <footer className="border-t border-slate-200 px-5 py-4 text-xs text-slate-600">
                    {pagination.total} matching quotation(s)
                </footer>
            </Card>

            <input
                ref={revisionInput}
                type="file"
                accept=".pdf,application/pdf"
                aria-label="Upload quotation revision"
                className="hidden"
                onChange={uploadRevision}
            />

            {mode && (
                <QuoteForm
                    mode={mode}
                    quotation={editing}
                    onClose={() => { setMode(null); setEditing(null); }}
                    onSave={addQuotation}
                />
            )}

            {preview && (
                <PdfViewer quotation={preview} onClose={() => setPreview(null)} />
            )}
        </div>
    );
}
