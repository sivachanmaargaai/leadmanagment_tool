import { useSettings } from "../context/SettingsContext";
import usePagination from "../hooks/usePagination";
import Pagination from "../components/Pagination";
import { useEffect, useState } from "react";
import {
    Plus,
    Search,
    Building2,
    Pencil,
    Eye,
    Trash2,
} from "lucide-react";
import { divisions } from "../data/crm";
import {
    belongsToCustomer,
    buildCustomerDirectory,
    normalise,
} from "../lib/customers";
import { getCustomers, createCustomer, updateCustomer, deleteCustomer } from "../services/customersApi";
import { getQuotations } from "../services/quotationsApi";
import PdfViewer from "../components/quotations/PdfViewer";
import {
    effectiveStatus,
    money,
} from "../lib/quotationPdf";
import { formatFollowUpDate } from "../lib/followUps";
import CustomerForm from "../components/CustomerForm";
import Modal from "../components/Modal";
import {
    Avatar,
    Button,
    Card,
    CardHeading,
    EmptyState,
    IconButton,
} from "../components/ui";

const selectClass =
    "min-w-0 rounded-lg border border-slate-300 bg-white px-3 py-2 text-xs font-medium text-slate-900 outline-none focus:border-teal-600 focus:ring-2 focus:ring-teal-100";

function StageBadge({ stage }) {
    return (
        <span
            className={`inline-block rounded-md px-2 py-1 text-[10px] font-semibold ${stage === "Converted Customer"
                ? "bg-emerald-50 text-emerald-900"
                : "bg-amber-50 text-amber-900"
                }`}
        >
            {stage}
        </span>
    );
}

function DetailRow({ label, children }) {
    return (
        <div className="min-w-0">
            <dt className="text-[11px] font-medium text-slate-600">{label}</dt>
            <dd className="mt-1 break-words text-xs leading-6 text-slate-950">
                {children || "Not added"}
            </dd>
        </div>
    );
}

function CustomerDetails({
    customer,
    leads,
    quotations,
    followUps,
    onClose,
    onEdit,
    onDelete,
}) {
    const [tab, setTab] = useState("Overview");
    const [pdf, setPdf] = useState(null);
    const [deleting, setDeleting] = useState(false);
    const [deleteError, setDeleteError] = useState("");

    async function removeCustomer() {
        if (deleting || !window.confirm(`Delete ${customer.name}? This removes the saved customer profile.`)) return;
        setDeleting(true);
        try { await onDelete(customer); }
        catch (error) { setDeleteError(error.message); }
        finally { setDeleting(false); }
    }

    const customerLeads = leads.filter((lead) =>
        belongsToCustomer(lead, customer)
    );

    const leadIds = new Set(customerLeads.map((lead) => lead.id));

    const customerQuotes = quotations.filter((quote) =>
        belongsToCustomer(quote, customer)
    );

    const customerFollowUps = followUps.filter(
        (item) =>
            leadIds.has(item.leadId) ||
            belongsToCustomer(item, customer)
    );

    const history = [
        ...(customer.history || []),
        ...customerFollowUps.flatMap((item) =>
            (item.history || []).map((entry) => ({
                ...entry,
                message: `${item.purpose}: ${entry.message}`,
            }))
        ),
        ...customerQuotes.flatMap((quote) =>
            quote.versions.map((version, index) => ({
                id: version.id,
                at: version.uploadedAt,
                message: `${quote.number} — PDF revision ${index + 1} saved.`,
            }))
        ),
    ].sort((a, b) => Date.parse(b.at) - Date.parse(a.at));

    return (
        <>
            <Modal title="Customer details" onClose={onClose}>
                <div className="p-4 sm:p-5">
                    <div className="flex flex-wrap items-start justify-between gap-3">
                        <div className="flex min-w-0 items-start gap-3">
                            <Avatar name={customer.name} />
                            <div className="min-w-0">
                                <h3 className="break-words text-base font-bold text-slate-950">
                                    {customer.name}
                                </h3>
                                <p className="mt-1 text-xs text-slate-700">
                                    {customer.type} · {customer.divisions.join(", ")}
                                </p>
                                <div className="mt-2">
                                    <StageBadge stage={customer.stage} />
                                </div>
                            </div>
                        </div>

                        <Button variant="secondary" disabled={deleting} onClick={onEdit}>
                            <Pencil size={15} /> Edit
                        </Button>
                    </div>

                    {onDelete && <div className="mt-3 flex flex-wrap items-center gap-3">
                        <Button variant="secondary" disabled={deleting} onClick={removeCustomer}><Trash2 size={15} />{deleting ? "Deleting..." : "Delete customer"}</Button>
                        {deleteError && <p role="alert" className="text-xs text-rose-800">{deleteError}</p>}
                    </div>}
                    <nav
                        aria-label="Customer detail sections"
                        className="my-5 flex gap-1 overflow-x-auto border-b border-slate-200 pb-3"
                    >
                        {[
                            "Overview",
                            "Contacts",
                            "Leads",
                            "Quotations",
                            "Follow-ups",
                            "History",
                        ].map((name) => (
                            <button
                                key={name}
                                type="button"
                                aria-pressed={tab === name}
                                onClick={() => setTab(name)}
                                className={`shrink-0 rounded-lg px-3 py-2 text-xs font-semibold transition-colors ${tab === name
                                    ? "bg-teal-900 text-white"
                                    : "text-slate-700 hover:bg-teal-50"
                                    }`}
                            >
                                {name}
                            </button>
                        ))}
                    </nav>

                    {tab === "Overview" && (
                        <div className="space-y-5">
                            <div className="grid grid-cols-3 gap-2">
                                {[
                                    ["Leads", customerLeads.length],
                                    ["Quotations", customerQuotes.length],
                                    [
                                        "Pending tasks",
                                        customerFollowUps.filter(
                                            (item) => item.status === "Pending"
                                        ).length,
                                    ],
                                ].map(([label, count]) => (
                                    <div
                                        key={label}
                                        className="rounded-xl border border-teal-100 bg-teal-50 p-3 shadow-sm"
                                    >
                                        <p className="text-[10px] font-medium text-teal-900">
                                            {label}
                                        </p>
                                        <strong className="mt-2 block text-xl text-teal-950">
                                            {count}
                                        </strong>
                                    </div>
                                ))}
                            </div>

                            <dl className="grid gap-4 sm:grid-cols-2">
                                <DetailRow label="Responsible staff">
                                    {customer.assignedTo}
                                </DetailRow>
                                <DetailRow label="Lead source">
                                    {customer.leadSource}
                                </DetailRow>
                                <DetailRow label="Referred by">
                                    {customer.referredBy?.name}
                                </DetailRow>
                                <DetailRow label="Reference company">
                                    {customer.referredBy?.company}
                                </DetailRow>
                                <DetailRow label="Reference contact">
                                    {[
                                        customer.referredBy?.phone,
                                        customer.referredBy?.email,
                                    ]
                                        .filter(Boolean)
                                        .join(" · ")}
                                </DetailRow>
                                <DetailRow label="GST number">{customer.gst}</DetailRow>
                                <DetailRow label="Address">
                                    {[
                                        customer.address,
                                        customer.city,
                                        customer.state,
                                        customer.postcode,
                                    ]
                                        .filter(Boolean)
                                        .join(", ")}
                                </DetailRow>
                                <DetailRow label="Reference notes">
                                    {customer.referenceNotes}
                                </DetailRow>
                            </dl>

                            {customer.notes && (
                                <div className="rounded-xl bg-slate-50 p-4">
                                    <h4 className="text-xs font-bold text-slate-900">
                                        Internal notes
                                    </h4>
                                    <p className="mt-2 whitespace-pre-wrap text-xs leading-6 text-slate-700">
                                        {customer.notes}
                                    </p>
                                </div>
                            )}
                        </div>
                    )}

                    {tab === "Contacts" && (
                        <div className="grid gap-3 sm:grid-cols-2">
                            {customer.contacts.map((contact, index) => (
                                <Card key={index} className="p-4">
                                    <p className="mb-2 text-[10px] font-semibold text-teal-800">
                                        {index === 0 ? "PRIMARY CONTACT" : "ADDITIONAL CONTACT"}
                                    </p>
                                    <strong className="text-sm text-slate-950">
                                        {contact.name || "Name not added"}
                                    </strong>
                                    <p className="mt-1 text-xs text-slate-700">
                                        {contact.designation}
                                    </p>

                                    <div className="mt-3 space-y-2 text-xs">
                                        {contact.phone && (
                                            <a
                                                href={`tel:${contact.phone.replace(/[^\d+]/g, "")}`}
                                                className="block break-all font-medium text-teal-800 hover:underline"
                                            >
                                                {contact.phone}
                                            </a>
                                        )}
                                        {contact.email && (
                                            <a
                                                href={`mailto:${contact.email}`}
                                                className="block break-all font-medium text-teal-800 hover:underline"
                                            >
                                                {contact.email}
                                            </a>
                                        )}
                                        {!contact.phone && !contact.email && (
                                            <p className="text-slate-600">
                                                Edit this profile to add phone/email.
                                            </p>
                                        )}
                                    </div>
                                </Card>
                            ))}
                        </div>
                    )}

                    {tab === "Leads" && (
                        <div className="space-y-3">
                            {customerLeads.map((lead) => (
                                <Card key={lead.id} className="p-4">
                                    <div className="flex flex-wrap justify-between gap-2">
                                        <strong className="text-xs text-slate-950">
                                            {lead.description}
                                        </strong>
                                        <span className="text-[11px] font-semibold text-teal-900">
                                            {lead.status}
                                        </span>
                                    </div>
                                    <p className="mt-2 text-xs text-slate-700">
                                        {lead.division} · {lead.priority} priority
                                    </p>
                                    <p className="mt-2 text-[11px] text-slate-600">
                                        Lead reference: {lead.referredBy?.name || "Not specified"}
                                    </p>
                                </Card>
                            ))}
                            {!customerLeads.length && (
                                <EmptyState title="No linked leads yet" />
                            )}
                        </div>
                    )}

                    {tab === "Quotations" && (
                        <div className="space-y-3">
                            {customerQuotes.map((quote) => (
                                <Card key={quote.id} className="p-4">
                                    <div className="flex flex-wrap items-center justify-between gap-3">
                                        <div>
                                            <strong className="text-xs text-slate-950">
                                                {quote.number}
                                            </strong>
                                            <p className="mt-1 text-xs text-slate-700">
                                                {quote.division} · {effectiveStatus(quote)}
                                            </p>
                                        </div>

                                        <Button
                                            variant="secondary"
                                            onClick={() => setPdf(quote)}
                                        >
                                            <Eye size={15} /> View PDF
                                        </Button>
                                    </div>

                                    {Object.entries(quote.totals).map(([billing, total]) => (
                                        <p key={billing} className="mt-2 text-xs text-teal-900">
                                            {billing}: {money(total.total, quote.currency)}
                                        </p>
                                    ))}
                                </Card>
                            ))}
                            {!customerQuotes.length && (
                                <EmptyState title="No linked quotations yet" />
                            )}
                        </div>
                    )}

                    {tab === "Follow-ups" && (
                        <div className="space-y-3">
                            {customerFollowUps.map((item) => (
                                <Card key={item.id} className="p-4">
                                    <div className="flex flex-wrap justify-between gap-2">
                                        <strong className="text-xs text-slate-950">
                                            {item.purpose}
                                        </strong>
                                        <span className="text-[11px] font-semibold text-teal-900">
                                            {item.status}
                                        </span>
                                    </div>
                                    <p className="mt-2 text-xs leading-6 text-slate-700">
                                        {formatFollowUpDate(item.dueAt)} IST
                                        <br />
                                        {item.type} · {item.assignedTo}
                                    </p>
                                    {item.completionNotes && (
                                        <p className="mt-2 text-xs leading-6 text-slate-700">
                                            {item.outcome}: {item.completionNotes}
                                        </p>
                                    )}
                                </Card>
                            ))}
                            {!customerFollowUps.length && (
                                <EmptyState title="No linked follow-ups yet" />
                            )}
                        </div>
                    )}

                    {tab === "History" && (
                        history.length ? (
                            <ol className="space-y-4 border-l border-teal-200 pl-4">
                                {history.map((entry) => (
                                    <li key={entry.id}>
                                        <p className="text-[11px] font-semibold text-teal-800">
                                            {formatFollowUpDate(entry.at)} IST
                                        </p>
                                        <p className="mt-1 whitespace-pre-wrap text-xs leading-6 text-slate-700">
                                            {entry.message}
                                        </p>
                                    </li>
                                ))}
                            </ol>
                        ) : (
                            <EmptyState title="No recorded activity yet" />
                        )
                    )}
                </div>
            </Modal>

            {pdf && (
                <PdfViewer quotation={pdf} onClose={() => setPdf(null)} />
            )}
        </>
    );
}

export default function Customers({ leads = [], followUps = [] }) {
    const { user: accessUser } = useSettings();
    const [saved, setSaved] = useState([]);
    const [error, setError] = useState("");
    const [loading, setLoading] = useState(true);
    const [reload, setReload] = useState(0);
    const [quoteError, setQuoteError] = useState("");
    const [quotations, setQuotations] = useState([]);
    const [search, setSearch] = useState("");
    const [division, setDivision] = useState("All divisions");
    const [type, setType] = useState("All types");
    const [editor, setEditor] = useState(null);
    const [selectedId, setSelectedId] = useState(null);
    const [notice, setNotice] = useState("");

    useEffect(() => {
        let active = true;
        getCustomers().then((records) => {
            if (active) { setSaved(records); setError(""); }
        }).catch((loadError) => {
            if (active) setError(loadError.message);
        }).finally(() => { if (active) setLoading(false); });
        return () => { active = false; };
    }, [reload]);

    useEffect(() => {
        let active = true;

        getQuotations()
            .then((records) => {
                if (active) setQuotations(records);
            })
            .catch(() => {
                if (active) {
                    setQuoteError(
                        "Quotation records could not be loaded. Customer details remain available."
                    );
                }
            });

        return () => {
            active = false;
        };
    }, []);

    const directory = buildCustomerDirectory(saved, leads, quotations);

    const scoped = directory.filter(
        (customer) =>
            division === "All divisions" ||
            customer.divisions.includes(division)
    );

    const filtered = scoped.filter((customer) => {
        const searchable = [
            customer.name,
            customer.referredBy?.name,
            customer.referredBy?.company,
            ...customer.contacts.flatMap((contact) => [
                contact.name,
                contact.phone,
                contact.email,
            ]),
        ]
            .filter(Boolean)
            .join(" ")
            .toLowerCase();

        return (
            (type === "All types" || customer.type === type) &&
            searchable.includes(search.trim().toLowerCase())
        );
    });

    const selected = directory.find(
        (customer) => customer.id === selectedId
    );

  const pagination = usePagination(filtered);
  const pageRows = pagination.rows;
    async function save(profile) {
        if (loading || error) throw new Error("Load the customer directory successfully before saving. Use Retry to reconnect.");
        const duplicate = directory.find(
            (customer) =>
                customer.id !== profile.id &&
                [customer.name, ...(customer.aliases || [])].some(
                    (name) => normalise(name) === normalise(profile.name)
                )
        );

        if (duplicate) {
            throw new Error(
                "This customer already exists. Open their profile to edit details."
            );
        }

        const exists = saved.some((customer) => customer.id === profile.id);
        const result = exists ? await updateCustomer(profile.id, profile) : await createCustomer(profile);
        setSaved((current) => exists ? current.map((customer) => customer.id === result.id ? result : customer) : [result, ...current]);
        setEditor(null);
        setSelectedId(result.id);
        setNotice("Customer saved to the database.");
    }

    async function removeCustomer(customer) {
        const linkedLeads = leads.filter((lead) => belongsToCustomer(lead, customer));
        const leadIds = new Set(linkedLeads.map((lead) => lead.id));
        const hasLinkedRecords = linkedLeads.length || quotations.some((quote) => belongsToCustomer(quote, customer)) || followUps.some((item) => leadIds.has(item.leadId) || belongsToCustomer(item, customer));
        if (hasLinkedRecords) throw new Error("This customer has linked records. Keep the profile until those records are reassigned or archived.");
        await deleteCustomer(customer.id, customer.version);
        setSaved((current) => current.filter((record) => record.id !== customer.id));
        setSelectedId(null);
        setNotice("Customer deleted from the database.");
    }

    return (
        <div className="space-y-4">
            <div className="flex flex-wrap items-center justify-between gap-3">
                <p className="max-w-xl text-xs leading-6 text-slate-700">
                    Contact details, references and customer conversations.
                    Existing leads and quotations are linked by customer name.
                </p>
                <Button disabled={loading || Boolean(error)} onClick={() => setEditor({ customer: null })}>
                    <Plus size={16} /> Add customer
                </Button>
            </div>

            <div className="grid grid-cols-2 gap-3 md:grid-cols-3">
                {[
                    ["Total customers", scoped.length],
                    [
                        "Prospects",
                        scoped.filter((customer) => customer.stage === "Prospect").length,
                    ],
                    [
                        "Converted customers",
                        scoped.filter(
                            (customer) => customer.stage === "Converted Customer"
                        ).length,
                    ],
                ].map(([label, value]) => (
                    <Card key={label} className="p-4">
                        <p className="text-xs font-semibold text-slate-700">{label}</p>
                        <strong className="mt-2 block text-2xl text-slate-950">
                            {value}
                        </strong>
                    </Card>
                ))}
            </div>

            {error && (
                <p role="alert" className="rounded-xl bg-amber-50 p-3 text-xs leading-6 text-amber-950">
                    {error} <button type="button" className="ml-2 font-semibold underline" onClick={() => { setLoading(true); setReload((value) => value + 1); }}>Retry</button>
                </p>
            )}

            {quoteError && <p role="alert" className="rounded-xl bg-amber-50 p-3 text-xs text-amber-950">{quoteError}</p>}
            {loading && <p role="status" className="rounded-xl bg-teal-50 p-3 text-xs text-teal-950">Loading customers from the database...</p>}
            {notice && (
                <p role="status" className="rounded-xl bg-teal-50 p-3 text-xs text-teal-950">
                    {notice}
                </p>
            )}

            <Card>
                <CardHeading
                    title="Customer directory"
                    description="One profile for every customer, across divisions."
                />

                <div className="flex flex-wrap gap-3 border-y border-slate-100 px-4 py-3">
                    <label className="flex min-w-0 flex-1 basis-full items-center gap-2 rounded-lg border border-slate-300 px-3 py-2 focus-within:ring-2 focus-within:ring-teal-100 sm:basis-48">
                        <Search size={16} className="shrink-0 text-slate-700" />
                        <input
                            aria-label="Search customers"
                            placeholder="Customer, contact or reference..."
                            value={search}
                            onChange={(event) => setSearch(event.target.value)}
                            className="min-w-0 w-full bg-transparent text-xs text-slate-950 outline-none placeholder:text-slate-500"
                        />
                    </label>

                    <select
                        aria-label="Filter customers by division"
                        value={division}
                        onChange={(event) => setDivision(event.target.value)}
                        className={selectClass}
                    >
                        <option>All divisions</option>
                        {divisions.map((name) => (
                            <option key={name}>{name}</option>
                        ))}
                    </select>

                    <select
                        aria-label="Filter customers by type"
                        value={type}
                        onChange={(event) => setType(event.target.value)}
                        className={selectClass}
                    >
                        <option>All types</option>
                        <option>Company</option>
                        <option>Individual</option>
                    </select>
                </div>

                {/* Mobile and tablet cards */}
                <div className="grid gap-3 p-3 sm:grid-cols-2 lg:hidden">
                    {pageRows.map((customer) => (
                        <Card key={customer.id} className="p-3">
                            <div className="flex items-start gap-3">
                                <Avatar name={customer.name} />
                                <div className="min-w-0">
                                    <button
                                        type="button"
                                        onClick={() => setSelectedId(customer.id)}
                                        className="break-words text-left text-sm font-bold text-slate-950 hover:text-teal-800"
                                    >
                                        {customer.name}
                                    </button>
                                    <p className="mt-1 text-[11px] text-slate-700">
                                        {customer.contacts[0]?.name || "Contact not added"}
                                    </p>
                                </div>
                            </div>

                            <div className="my-3">
                                <StageBadge stage={customer.stage} />
                            </div>

                            <p className="break-all text-xs leading-6 text-slate-700">
                                {customer.contacts[0]?.phone ||
                                    customer.contacts[0]?.email ||
                                    "Phone / email not added"}
                            </p>

                            <p className="mt-2 text-[11px] leading-5 text-slate-700">
                                {customer.divisions.join(", ")}
                                <br />
                                Reference: {customer.referredBy?.name || "Not specified"}
                            </p>

                            <div className="mt-3 flex items-center justify-between border-t border-slate-100 pt-2">
                                <span className="text-[11px] text-slate-600">
                                    {customer.leadCount} lead(s)
                                </span>
                                <Button
                                    variant="secondary"
                                    onClick={() => setSelectedId(customer.id)}
                                >
                                    View profile
                                </Button>
                            </div>
                        </Card>
                    ))}
                </div>

                {/* Desktop table */}
                <div className="hidden overflow-x-auto lg:block">
                    <table className="w-full whitespace-nowrap text-left">
                        <thead className="border-b border-slate-200 bg-slate-50 text-[10px] uppercase tracking-wide text-slate-700">
                            <tr>
                                {[
                                    "Customer",
                                    "Contact",
                                    "Divisions",
                                    "Referred by",
                                    "Stage",
                                    "Actions",
                                ].map((heading) => (
                                    <th key={heading} className="px-4 py-3">{heading}</th>
                                ))}
                            </tr>
                        </thead>

                        <tbody className="divide-y divide-slate-100">
                            {pageRows.map((customer) => (
                                <tr key={customer.id} className="text-xs text-slate-700 hover:bg-teal-50/40">
                                    <td className="px-4 py-4">
                                        <button
                                            type="button"
                                            onClick={() => setSelectedId(customer.id)}
                                            className="flex items-center gap-3 text-left"
                                        >
                                            <Avatar name={customer.name} />
                                            <span>
                                                <strong className="block font-semibold text-slate-950">
                                                    {customer.name}
                                                </strong>
                                                <small className="mt-1 block text-slate-600">
                                                    {customer.type} · {customer.leadCount} leads
                                                </small>
                                            </span>
                                        </button>
                                    </td>
                                    <td className="px-4 py-4">
                                        <strong className="block text-slate-900">
                                            {customer.contacts[0]?.name || "Not added"}
                                        </strong>
                                        <small className="mt-1 block">
                                            {customer.contacts[0]?.phone ||
                                                customer.contacts[0]?.email ||
                                                "Phone / email not added"}
                                        </small>
                                    </td>
                                    <td className="px-4 py-4">
                                        {customer.divisions.join(", ")}
                                    </td>
                                    <td className="px-4 py-4">
                                        {customer.referredBy?.name || "Not specified"}
                                    </td>
                                    <td className="px-4 py-4">
                                        <StageBadge stage={customer.stage} />
                                    </td>
                                    <td className="px-4 py-4">
                                        <div className="flex gap-1">
                                            <IconButton
                                                aria-label={`View ${customer.name}`}
                                                onClick={() => setSelectedId(customer.id)}
                                            >
                                                <Eye size={16} />
                                            </IconButton>
                                            <IconButton
                                                aria-label={`Edit ${customer.name}`}
                                                onClick={() => setEditor({ customer })}
                                            >
                                                <Pencil size={16} />
                                            </IconButton>
                                        </div>
                                    </td>
                                </tr>
                            ))}
                        </tbody>
                    </table>
                </div>

        {!loading && !filtered.length && (
                    <EmptyState
                        icon={Building2}
                        title="No customers found"
                        description="Add a customer or adjust your filters."
                    />
                )}

                <Pagination pagination={pagination} />
                <footer className="border-t border-slate-200 px-4 py-3 text-xs text-slate-600">
                    {filtered.length} matching customer(s)
                </footer>
            </Card>

            {selected && (
                <CustomerDetails
                    customer={selected}
                    leads={leads}
                    quotations={quotations}
                    followUps={followUps}
                    onClose={() => setSelectedId(null)}
                    onEdit={() => {
                        setSelectedId(null);
                        setEditor({ customer: selected });
                    }}
                    onDelete={accessUser.role === "Admin" && saved.some((customer) => customer.id === selected.id) ? removeCustomer : undefined}
                />
            )}

            {editor && (
                <CustomerForm
                    customer={editor.customer}
                    onSave={save}
                    onClose={() => setEditor(null)}
                />
            )}
        </div>
    );
}
