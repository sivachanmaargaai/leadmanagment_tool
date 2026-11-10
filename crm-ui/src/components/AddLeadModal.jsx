import { useEffect, useRef, useState } from "react";
import { Plus, X } from "lucide-react";
import { divisionLabel, divisions } from "../data/crm";
import { Button, IconButton } from "./ui";
import CustomerField from "./CustomerField";
import ReferralFields from "./ReferralFields";
import { runtimeSettings } from "../lib/runtimeSettings";

const fieldClass =
    "w-full rounded-lg border border-slate-300 bg-white px-3 py-2.5 text-sm font-normal text-slate-950 outline-none placeholder:text-slate-500 focus:border-teal-600 focus:ring-2 focus:ring-teal-100";

const labelClass =
    "flex min-w-0 flex-col gap-2 text-xs font-semibold text-slate-800";

export default function AddLeadModal({ onClose, onSave, saveError = "", saving = false }) {
    const preferences = runtimeSettings();
    const dialogRef = useRef(null);
    const [customerLink, setCustomerLink] = useState({ customer: "", customerId: null });
    const [error, setError] = useState("");

    useEffect(() => {
        if (!dialogRef.current.open) {
            dialogRef.current.showModal();
        }
    }, []);

    function handleSubmit(event) {
        event.preventDefault();
        if (saving) return;

        const data = new FormData(event.currentTarget);
        const customer = String(data.get("customer")).trim();
        const description = String(data.get("description")).trim();

        if (!customer || (preferences.leads.requireDescription && !description)) {
            setError("Enter a customer name and requirement.");
            return;
        }

        const leadSource = String(data.get("leadSource") || "Direct Enquiry");
        const needsReference = ["Referral", "Known Network"].includes(leadSource);
        const referenceId = String(data.get("referredById") || "");

        if (needsReference && !referenceId) {
            setError("Select or add a reference contact.");
            return;
        }

        setError("");
        onSave({
            id: crypto.randomUUID(),
            customer,
            customerId: customerLink.customerId,
            description,
            contact: String(data.get("contact")).trim(),
            division: String(data.get("division")),
            priority: String(data.get("priority")),
            status: preferences.leads.defaultStatus,
            leadSource,
            referredBy: needsReference ? {
                id: referenceId,
                name: String(data.get("referredByName") || ""),
                company: String(data.get("referredByCompany") || ""),
                phone: String(data.get("referredByPhone") || ""),
                email: String(data.get("referredByEmail") || ""),
            } : null,
            referenceNotes: needsReference ? String(data.get("referenceNotes") || "").trim() : "",
        });
    }

    return (
        <dialog
            ref={dialogRef}
            aria-labelledby="lead-dialog-title"
            className="m-auto max-h-[94dvh] w-[calc(100%-1rem)] max-w-xl overflow-y-auto rounded-2xl border border-slate-200 bg-white p-0 text-slate-900 shadow-2xl backdrop:bg-slate-950/40 backdrop:backdrop-blur-sm"
            onCancel={(event) => {
                event.preventDefault();
                if (!saving) onClose();
            }}
            onClick={(event) => {
                if (!saving && event.target === event.currentTarget) onClose();
            }}
        >
            <div>
                <header className="flex items-start justify-between gap-4 border-b border-slate-200 p-4 sm:p-5">
                    <div>
                        <p className="text-[10px] font-bold tracking-[0.18em] text-teal-800">
                            NEW OPPORTUNITY
                        </p>
                        <h2
                            id="lead-dialog-title"
                            className="mt-2 text-xl font-bold text-slate-950"
                        >
                            Add a lead
                        </h2>
                        <p className="mt-2 text-xs leading-5 text-slate-700">
                            Start with the essentials. Build the relationship.
                        </p>
                    </div>

                    <IconButton aria-label="Close form" disabled={saving} onClick={onClose}>
                        <X size={21} />
                    </IconButton>
                </header>

                <form onSubmit={handleSubmit}>
                    <fieldset disabled={saving} className="min-w-0">
                    <div className="grid gap-4 p-4 sm:grid-cols-2 sm:p-5">
                        <div className={labelClass}>
                            <span>Customer / company *</span>
                            <CustomerField {...customerLink} onChange={setCustomerLink} maxLength={120} />
                        </div>

                        <label className={labelClass}>
                            Contact person
                            <input
                                name="contact"
                                required={preferences.leads.requireContact}
                                placeholder="Customer name"
                                maxLength={80}
                                className={fieldClass}
                            />
                        </label>

                        <label className={labelClass}>
                            Division *
                            <select
                                name="division"
                                defaultValue={preferences.workspace.defaultDivision === "All divisions" ? "nemilink" : preferences.workspace.defaultDivision}
                                className={fieldClass}
                            >
                                {divisions.map((division) => (
                                    <option key={division} value={division}>{divisionLabel(division)}</option>
                                ))}
                            </select>
                        </label>

                        <label className={labelClass}>
                            Priority *
                            <select
                                name="priority"
                                defaultValue={preferences.leads.defaultPriority}
                                className={fieldClass}
                            >
                                <option>High</option>
                                <option>Medium</option>
                                <option>Low</option>
                            </select>
                        </label>

                        <ReferralFields />

                        <label className={`${labelClass} sm:col-span-2`}>
                            Requirement *
                            <textarea
                                name="description"
                                placeholder="Describe the embedded, IoT or software requirement..."
                                required={preferences.leads.requireDescription}
                                rows={4}
                                maxLength={500}
                                className={`${fieldClass} resize-y`}
                            />
                        </label>

                        {(error || saveError) && (
                            <p
                                role="alert"
                                className="text-xs font-medium text-rose-800 sm:col-span-2"
                            >
                                {error || saveError}
                            </p>
                        )}
                    </div>

                    <footer className="flex justify-end gap-3 border-t border-slate-200 bg-slate-50 px-6 py-4">
                        <Button variant="secondary" onClick={onClose}>
                            Cancel
                        </Button>
                        <Button type="submit" disabled={saving}>
                            <Plus size={16} /> {saving ? "Saving..." : "Create lead"}
                        </Button>
                    </footer>
                    </fieldset>
                </form>
            </div>
        </dialog>
    );
}
