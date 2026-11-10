import usePagination from "../hooks/usePagination";
import Pagination from "./Pagination";
import { divisionLabel } from "../data/crm";

import { useState } from "react";
import {
    Search,
    ArrowRight,
    Flag,
    Pencil,
    Trash2,
    Check,
    X,
} from "lucide-react";

import { Card, CardHeading, Avatar, EmptyState } from "./ui";

const statusOptions = [
    "New",
    "In Progress",
    "Follow-up",
    "Won",
    "Lost",
];

const priorityOptions = ["High", "Medium", "Low"];

const statusStyles = {
    New: "bg-teal-50 text-teal-900 ring-teal-200",
    "In Progress": "bg-amber-50 text-amber-900 ring-amber-200",
    "Follow-up": "bg-sky-50 text-sky-900 ring-sky-200",
    Won: "bg-emerald-50 text-emerald-900 ring-emerald-200",
    Lost: "bg-rose-50 text-rose-900 ring-rose-200",
};

const priorityStyles = {
    High: "text-rose-700",
    Medium: "text-amber-800",
    Low: "text-emerald-800",
};

export default function LeadTable({
    leads = [],
    compact = false,
    onViewAll,
    onUpdateLead,
    onDeleteLead,
    remote,
}) {
    const [localSearch, setLocalSearch] = useState("");
    const search = remote ? remote.search : localSearch;
    const setSearch = remote ? remote.setSearch : setLocalSearch;
    const [editingId, setEditingId] = useState(null);
    const [editVersion, setEditVersion] = useState(null);
    const [editStatus, setEditStatus] = useState("New");
    const [editPriority, setEditPriority] = useState("Medium");
    const [savingId, setSavingId] = useState(null);
    const [actionError, setActionError] = useState("");

    const canManage = Boolean(
        !compact && onUpdateLead && !remote?.pagination.loading
    );

    // START EDIT
    function startEdit(lead) {
        if (!canManage || savingId !== null) return;

        setEditingId(lead.id);
        setEditVersion(lead.version);
        setEditStatus(lead.status);
        setEditPriority(lead.priority);
        setActionError("");
    }

    // CANCEL EDIT
    function cancelEdit() {
        if (savingId !== null) return;

        setEditingId(null);
        setActionError("");
    }

    // UPDATE LEAD API
    async function saveEdit(id) {
        if (!onUpdateLead || savingId !== null) return;

        setSavingId(id);
        setActionError("");

        try {
            await onUpdateLead(id, {
                status: editStatus,
                expectedVersion: editVersion,
                priority: editPriority,
            });

            setEditingId(null);
        } catch (error) {
            setActionError(
                error.message || "Unable to update lead"
            );
        } finally {
            setSavingId(null);
        }
    }

    // DELETE LEAD API
    async function removeLead(lead) {
        if (!onDeleteLead || savingId !== null) return;

        const confirmed = window.confirm(
            `Are you sure you want to delete ${lead.customer}?`
        );

        if (!confirmed) return;

        setSavingId(lead.id);
        setActionError("");

        try {
            const success = await onDeleteLead(lead.id, lead.version);

            if (!success) {
                setActionError("Unable to delete lead");
            } else if (editingId === lead.id) {
                setEditingId(null);
            }
        } catch (error) {
            setActionError(
                error.message || "Unable to delete lead"
            );
        } finally {
            setSavingId(null);
        }
    }

    // SEARCH FILTER
    const filtered = remote ? leads : leads.filter((lead) =>
        [
            lead.customer,
            lead.contact,
            divisionLabel(lead.division),
            lead.description,
            lead.status,
            lead.priority,
            lead.leadSource,
            lead.referredBy?.name,
            lead.referredBy?.company,
            lead.referredBy?.phone,
            lead.referredBy?.email,
        ]
            .filter(Boolean)
            .join(" ")
            .toLowerCase()
            .includes(search.trim().toLowerCase())
    );

    const localPagination = usePagination(filtered);
    const pagination = remote ? remote.pagination : localPagination;
    const displayed = compact
        ? filtered.slice(0, 5)
        : pagination.rows;

    return (
        <Card>
            {/* HEADER */}
            <CardHeading
                title={compact ? "Recent leads" : "All leads"}
                description="Track every customer conversation."
            >
                <label className="flex w-full items-center gap-2 rounded-lg border border-slate-300 bg-white px-3 py-2 text-slate-600 transition-colors focus-within:border-teal-600 focus-within:ring-2 focus-within:ring-teal-100 sm:w-auto">
                    <Search size={16} />

                    <input
                        aria-label="Search leads"
                        placeholder="Search leads..."
                        value={search}
                        onChange={(event) =>
                            setSearch(event.target.value)
                        }
                        className="w-full bg-transparent text-xs text-slate-900 outline-none placeholder:text-slate-500 sm:w-40"
                    />
                </label>
            </CardHeading>

            {/* API ERROR MESSAGE */}
            {actionError && (
                <div
                    role="alert"
                    className="mx-3 mb-3 rounded-lg bg-red-50 p-3 text-xs text-red-700"
                >
                    {actionError}
                </div>
            )}

            {/* MOBILE CARDS */}
            <div className="grid gap-3 px-3 pb-3 sm:grid-cols-2 lg:hidden">
                {displayed.map((lead) => (
                    <article
                        key={lead.id}
                        className="min-w-0 rounded-xl border border-slate-200 bg-white p-3 shadow-sm shadow-slate-900/5 transition-shadow duration-200 hover:shadow-md"
                    >
                        <div className="flex items-start gap-2.5">
                            <Avatar name={lead.customer} />

                            <div className="min-w-0">
                                <strong className="block break-words text-xs font-semibold text-slate-950">
                                    {lead.customer}
                                </strong>

                                <p className="mt-1 text-[11px] text-slate-600">
                                    {lead.contact || "Contact not added"}
                                </p>
                            </div>
                        </div>

                        <p className="my-3 break-words text-xs leading-5 text-slate-700">
                            {lead.description}
                        </p>

                        <div className="flex flex-wrap items-center gap-2">
                            <span
                                className={`rounded-md px-2 py-1 text-[10px] font-semibold ring-1 ring-inset ${statusStyles[lead.status] ||
                                    "bg-slate-100 text-slate-900 ring-slate-200"
                                    }`}
                            >
                                {lead.status}
                            </span>

                            <span
                                className={`inline-flex items-center gap-1 text-[11px] font-semibold ${priorityStyles[lead.priority] ||
                                    "text-slate-700"
                                    }`}
                            >
                                <Flag size={11} />
                                {lead.priority}
                            </span>
                        </div>

                        <dl className="mt-3 space-y-1.5 border-t border-slate-100 pt-3 text-[11px]">
                            <div className="flex justify-between gap-3">
                                <dt className="text-slate-600">
                                    Division
                                </dt>

                                <dd className="text-right font-medium text-slate-900">
                                    {divisionLabel(lead.division)}
                                </dd>
                            </div>

                            <div className="flex justify-between gap-3">
                                <dt className="shrink-0 text-slate-600">
                                    Referred by
                                </dt>

                                <dd className="min-w-0 break-words text-right font-medium text-teal-900">
                                    {lead.referredBy?.name ||
                                        lead.leadSource ||
                                        "Not specified"}
                                </dd>
                            </div>
                        </dl>

                        {/* MOBILE EDIT / DELETE */}
                        {canManage && (
                            <div className="mt-3 border-t border-slate-100 pt-3">
                                {editingId === lead.id ? (
                                    <div className="space-y-2">
                                        <label className="block text-xs font-semibold">
                                            Status
                                        </label>

                                        <select
                                            value={editStatus}
                                            disabled={savingId !== null}
                                            onChange={(e) =>
                                                setEditStatus(e.target.value)
                                            }
                                            className="w-full rounded-lg border border-slate-300 bg-white p-2 text-xs"
                                        >
                                            {statusOptions.map((status) => (
                                                <option key={status} value={status}>
                                                    {status}
                                                </option>
                                            ))}
                                        </select>

                                        <label className="block text-xs font-semibold">
                                            Priority
                                        </label>

                                        <select
                                            value={editPriority}
                                            disabled={savingId !== null}
                                            onChange={(e) =>
                                                setEditPriority(e.target.value)
                                            }
                                            className="w-full rounded-lg border border-slate-300 bg-white p-2 text-xs"
                                        >
                                            {priorityOptions.map((priority) => (
                                                <option key={priority} value={priority}>
                                                    {priority}
                                                </option>
                                            ))}
                                        </select>

                                        <div className="flex gap-2 pt-2">
                                            <button
                                                type="button"
                                                disabled={savingId !== null}
                                                onClick={() => saveEdit(lead.id)}
                                                className="flex items-center gap-1 rounded-lg bg-teal-700 px-3 py-2 text-xs font-semibold text-white disabled:opacity-50"
                                            >
                                                <Check size={14} />
                                                {savingId === lead.id
                                                    ? "Saving..."
                                                    : "Save"}
                                            </button>

                                            <button
                                                type="button"
                                                disabled={savingId !== null}
                                                onClick={cancelEdit}
                                                className="flex items-center gap-1 rounded-lg border border-slate-300 px-3 py-2 text-xs disabled:opacity-50"
                                            >
                                                <X size={14} />
                                                Cancel
                                            </button>
                                        </div>
                                    </div>
                                ) : (
                                    <div className="flex gap-2">
                                        <button
                                            type="button"
                                            disabled={savingId !== null}
                                            onClick={() => startEdit(lead)}
                                            className="flex items-center gap-1 rounded-lg border border-slate-300 px-3 py-2 text-xs text-teal-800 disabled:opacity-50"
                                        >
                                            <Pencil size={13} />
                                            Edit
                                        </button>

                                        {onDeleteLead && <button
                                            type="button"
                                            disabled={savingId !== null}
                                            onClick={() => removeLead(lead)}
                                            className="flex items-center gap-1 rounded-lg border border-rose-200 px-3 py-2 text-xs text-rose-700 disabled:opacity-50"
                                        >
                                            <Trash2 size={13} />
                                            {savingId === lead.id
                                                ? "Deleting..."
                                                : "Delete"}
                                        </button>}
                                    </div>
                                )}
                            </div>
                        )}
                    </article>
                ))}
            </div>

            {/* DESKTOP TABLE */}
            <div className="hidden overflow-x-auto lg:block">
                <table className="w-full border-collapse whitespace-nowrap text-left">
                    <thead className="border-y border-slate-200 bg-slate-50 text-[10px] font-bold uppercase tracking-wider text-slate-700">
                        <tr>
                            {[
                                "Customer",
                                "Division",
                                "Referred By",
                                "Requirement",
                                "Status",
                                "Priority",
                                ...(canManage ? ["Actions"] : []),
                            ].map((label) => (
                                <th key={label} className="px-5 py-3">
                                    {label}
                                </th>
                            ))}
                        </tr>
                    </thead>

                    <tbody className="divide-y divide-slate-100">
                        {displayed.map((lead) => (
                            <tr
                                key={lead.id}
                                className="text-xs text-slate-700 transition-colors hover:bg-teal-50/50"
                            >
                                {/* CUSTOMER */}
                                <td className="px-5 py-4">
                                    <div className="flex items-center gap-3">
                                        <Avatar name={lead.customer} />

                                        <div>
                                            <strong className="block font-semibold text-slate-950">
                                                {lead.customer}
                                            </strong>

                                            <small className="mt-1 block text-[11px] text-slate-600">
                                                {lead.contact || "Contact not added"}
                                            </small>
                                        </div>
                                    </div>
                                </td>

                                {/* DIVISION */}
                                <td className="px-5 py-4 font-medium text-slate-800">
                                    {divisionLabel(lead.division)}
                                </td>

                                {/* REFERRED BY */}
                                <td className="px-5 py-4">
                                    {lead.referredBy ? (
                                        <div>
                                            <strong className="block text-xs font-semibold text-slate-950">
                                                {lead.referredBy.name}
                                            </strong>

                                            {lead.referredBy.company && (
                                                <small className="mt-1 block text-[11px] text-slate-700">
                                                    {lead.referredBy.company}
                                                </small>
                                            )}

                                            <span className="mt-1 inline-block rounded-md bg-teal-50 px-2 py-1 text-[10px] font-semibold text-teal-900">
                                                {lead.leadSource}
                                            </span>
                                        </div>
                                    ) : (
                                        <span className="text-xs text-slate-600">
                                            {lead.leadSource || "Not specified"}
                                        </span>
                                    )}
                                </td>

                                {/* REQUIREMENT */}
                                <td className="max-w-xs whitespace-normal break-words px-5 py-4">
                                    {lead.description}
                                </td>

                                {/* STATUS */}
                                <td className="px-5 py-4">
                                    {editingId === lead.id && canManage ? (
                                        <select
                                            value={editStatus}
                                            disabled={savingId !== null}
                                            onChange={(e) =>
                                                setEditStatus(e.target.value)
                                            }
                                            className="rounded-lg border border-slate-300 bg-white px-2 py-2 text-xs"
                                        >
                                            {statusOptions.map((status) => (
                                                <option key={status} value={status}>
                                                    {status}
                                                </option>
                                            ))}
                                        </select>
                                    ) : (
                                        <span
                                            className={`inline-flex items-center gap-1.5 rounded-md px-2 py-1 text-[10px] font-semibold ring-1 ring-inset ${statusStyles[lead.status] ||
                                                "bg-slate-100 text-slate-900 ring-slate-200"
                                                }`}
                                        >
                                            <i className="size-1 rounded-full bg-current" />
                                            {lead.status}
                                        </span>
                                    )}
                                </td>

                                {/* PRIORITY */}
                                <td className="px-5 py-4">
                                    {editingId === lead.id && canManage ? (
                                        <select
                                            value={editPriority}
                                            disabled={savingId !== null}
                                            onChange={(e) =>
                                                setEditPriority(e.target.value)
                                            }
                                            className="rounded-lg border border-slate-300 bg-white px-2 py-2 text-xs"
                                        >
                                            {priorityOptions.map((priority) => (
                                                <option key={priority} value={priority}>
                                                    {priority}
                                                </option>
                                            ))}
                                        </select>
                                    ) : (
                                        <span
                                            className={`inline-flex items-center gap-1.5 text-[11px] font-semibold ${priorityStyles[lead.priority] ||
                                                "text-slate-700"
                                                }`}
                                        >
                                            <Flag size={12} />
                                            {lead.priority}
                                        </span>
                                    )}
                                </td>

                                {/* ACTIONS */}
                                {canManage && (
                                    <td className="px-5 py-4">
                                        <div className="flex items-center gap-2">
                                            {editingId === lead.id ? (
                                                <>
                                                    <button
                                                        type="button"
                                                        title="Save changes"
                                                        aria-label="Save lead changes"
                                                        disabled={savingId !== null}
                                                        onClick={() => saveEdit(lead.id)}
                                                        className="rounded-lg p-2 text-emerald-700 hover:bg-emerald-50 disabled:opacity-50"
                                                    >
                                                        <Check size={16} />
                                                    </button>

                                                    <button
                                                        type="button"
                                                        title="Cancel editing"
                                                        aria-label="Cancel editing"
                                                        disabled={savingId !== null}
                                                        onClick={cancelEdit}
                                                        className="rounded-lg p-2 text-slate-600 hover:bg-slate-100 disabled:opacity-50"
                                                    >
                                                        <X size={16} />
                                                    </button>
                                                </>
                                            ) : (
                                                <>
                                                    <button
                                                        type="button"
                                                        title="Edit lead"
                                                        aria-label={`Edit ${lead.customer}`}
                                                        disabled={savingId !== null}
                                                        onClick={() => startEdit(lead)}
                                                        className="rounded-lg p-2 text-teal-700 hover:bg-teal-50 disabled:opacity-50"
                                                    >
                                                        <Pencil size={16} />
                                                    </button>

                                                    {onDeleteLead && <button
                                                        type="button"
                                                        title="Delete lead"
                                                        aria-label={`Delete ${lead.customer}`}
                                                        disabled={savingId !== null}
                                                        onClick={() => removeLead(lead)}
                                                        className="rounded-lg p-2 text-rose-700 hover:bg-rose-50 disabled:opacity-50"
                                                    >
                                                        <Trash2 size={16} />
                                                    </button>}
                                                </>
                                            )}
                                        </div>
                                    </td>
                                )}
                            </tr>
                        ))}
                    </tbody>
                </table>
            </div>

            {/* EMPTY STATE */}
            {displayed.length === 0 && (
                <EmptyState
                    icon={Search}
                    title="No matching leads"
                    description="Try another customer name or requirement."
                />
            )}

            {!compact && <Pagination pagination={pagination} />}
            {/* FOOTER */}
            <footer className="flex items-center justify-between gap-4 border-t border-slate-200 px-5 py-4 text-[11px] text-slate-600">
                <span>
                    Showing {displayed.length} of {remote ? pagination.total : filtered.length} leads
                </span>

                {compact && (
                    <button
                        type="button"
                        onClick={onViewAll}
                        className="inline-flex items-center gap-1.5 font-semibold text-teal-800 hover:text-teal-950 hover:underline focus-visible:outline-2 focus-visible:outline-teal-700"
                    >
                        View all leads
                        <ArrowRight size={14} />
                    </button>
                )}
            </footer>
        </Card>
    );
}
