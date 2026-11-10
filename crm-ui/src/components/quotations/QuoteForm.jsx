import { useRef, useState } from "react";
import { Plus, Trash2, Save } from "lucide-react";
import { divisionLabel, divisions } from "../../data/crm";
import { Button, IconButton } from "../ui";
import CustomerField from "../CustomerField";
import QuoteDialog from "./QuoteDialog";
import { runtimeSettings } from "../../lib/runtimeSettings";
import {
    billingTypes,
    quoteStatuses,
    today,
    money,
    calculateTotals,
    validatePdf,
} from "../../lib/quotationPdf";

const fieldClass =
    "w-full rounded-lg border border-slate-300 bg-white px-3 py-2.5 text-sm text-slate-950 outline-none placeholder:text-slate-500 focus:border-teal-600 focus:ring-2 focus:ring-teal-100";

function Field({ label, children }) {
    return (
        <label className="block min-w-0">
            <span className="mb-2 block text-xs font-semibold text-slate-800">
                {label}
            </span>
            {children}
        </label>
    );
}

function newItem() {
    return {
        id: crypto.randomUUID(),
        description: "",
        quantity: "1",
        rate: "",
        billing: "One-time",
    };
}

export default function QuoteForm({ mode, quotation, onClose, onSave }) {
    const isUpload = mode === "upload" || mode === "revision";
    const defaults = runtimeSettings().quotation;
    const submitting = useRef(false);

    const [form, setForm] = useState(() => ({
        number: "",
        customer: "",
        customerId: null,
        contact: "",
        address: "",
        division: divisions[0],
        date: today(),
        validUntil: new Date(Date.parse(`${today()}T00:00:00Z`) + defaults.validity * 86400000).toISOString().slice(0, 10),
        status: "Draft",
        currency: defaults.currency,
        amount: "",
        billing: "One-time",
        tax: isUpload ? "0" : String(defaults.tax),
        terms: [defaults.paymentTerms, defaults.warranty, defaults.notes].filter(Boolean).join("\n"),
        ...quotation,
    }));

    const [items, setItems] = useState(() => quotation?.items?.map((item) => ({ ...item, id: crypto.randomUUID() })) || [newItem()]);
    const [file, setFile] = useState(null);
    const [error, setError] = useState("");
    const [busy, setBusy] = useState(false);

    const totals = calculateTotals(items, form.tax);

    function update(field, value) {
        setForm((current) => ({ ...current, [field]: value }));
    }

    function bind(field) {
        return {
            value: form[field],
            onChange: (event) => update(field, event.target.value),
        };
    }

    function updateItem(id, field, value) {
        setItems((current) =>
            current.map((item) =>
                item.id === id ? { ...item, [field]: value } : item
            )
        );
    }

    async function submit(event) {
        event.preventDefault();
        if (submitting.current) return;
        setError("");

        if (!form.customer.trim() || (isUpload && !form.number.trim())) {
            setError("Enter the customer and the quotation number for an uploaded PDF.");
            return;
        }

        if (form.validUntil < form.date) {
            setError("Valid-until date must be on or after the quotation date.");
            return;
        }

        if (
            !isUpload &&
            items.some(
                (item) =>
                    !item.description.trim() ||
                    !Number.isFinite(Number(item.quantity)) ||
                    Number(item.quantity) <= 0 ||
                    item.rate === "" ||
                    !Number.isFinite(Number(item.rate)) ||
                    Number(item.rate) < 0
            )
        ) {
            setError("Enter a description, positive quantity and valid rate for each item.");
            return;
        }

        submitting.current = true;
        setBusy(true);

        try {
            if (isUpload) await validatePdf(file);

            const draft = {
                ...form,
                id: crypto.randomUUID(),
                number: form.number.trim(),
                customer: form.customer.trim(),
                source: isUpload ? "Uploaded" : "Created",
                items: isUpload ? [] : items,
                tax: Number(form.tax),
                totals: isUpload
                    ? {
                        [form.billing]: {
                            subtotal: Number(form.amount),
                            tax: 0,
                            total: Number(form.amount),
                        },
                    }
                    : totals,
                createdAt: new Date().toISOString(),
            };

            await onSave(draft, isUpload ? file : null);
        } catch (saveError) {
            setError(saveError.message || "Could not save the quotation.");
        } finally {
            setBusy(false);
            submitting.current = false;
        }
    }

    return (
        <QuoteDialog
            title={mode === "revision" ? "Revise details & upload replacement PDF" : isUpload ? "Upload existing quotation" : quotation ? "Edit quotation · creates a new PDF revision" : "Create quotation"}
            onClose={busy ? () => { } : onClose}
        >
            <form onSubmit={submit}>
                <fieldset disabled={busy} className="min-w-0 space-y-4 p-4 sm:p-5">
                    <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
                        <div className="min-w-0"><span className="mb-2 block text-xs font-semibold text-slate-800">Customer / company *</span>
                            <CustomerField customer={form.customer} customerId={form.customerId} onChange={(link) => setForm((current) => ({ ...current, ...link }))} />
                        </div>

                        <Field label="Contact person">
                            <input
                                maxLength={80}
                                className={fieldClass}
                                {...bind("contact")}
                            />
                        </Field>

                        <Field label="Division">
                            <select className={fieldClass} {...bind("division")}>
                                {divisions.map((division) => (
                                    <option key={division} value={division}>{divisionLabel(division)}</option>
                                ))}
                            </select>
                        </Field>

                        <Field label={isUpload ? "Quotation number *" : "Quotation number (blank = automatic)"}>
                            <input
                                required={isUpload}
                                placeholder={isUpload ? "Number shown in the PDF" : "Assigned when saved"}
                                maxLength={50}
                                className={fieldClass}
                                {...bind("number")}
                            />
                        </Field>

                        <Field label="Quotation date *">
                            <input
                                required
                                type="date"
                                className={fieldClass}
                                {...bind("date")}
                            />
                        </Field>

                        <Field label="Valid until *">
                            <input
                                required
                                type="date"
                                min={form.date}
                                className={fieldClass}
                                {...bind("validUntil")}
                            />
                        </Field>

                        <Field label="Status">
                            <select className={fieldClass} {...bind("status")}>
                                {quoteStatuses.map((status) => (
                                    <option key={status}>{status}</option>
                                ))}
                            </select>
                        </Field>

                        <Field label="Currency">
                            <select className={fieldClass} {...bind("currency")}>
                                {["INR", "USD", "EUR"].map((currency) => (
                                    <option key={currency}>{currency}</option>
                                ))}
                            </select>
                        </Field>
                    </div>

                    <Field label="Customer address">
                        <textarea
                            rows={2}
                            maxLength={400}
                            className={`${fieldClass} resize-y`}
                            {...bind("address")}
                        />
                    </Field>

                    {isUpload ? (
                        <div className="space-y-5 rounded-xl border border-teal-200 bg-teal-50/40 p-5">
                            <div className="grid gap-4 sm:grid-cols-2">
                                <Field label="Quoted amount — as shown in PDF *">
                                    <input
                                        required
                                        type="number"
                                        min="0"
                                        step="0.01"
                                        className={fieldClass}
                                        {...bind("amount")}
                                    />
                                </Field>

                                <Field label="Amount billing basis">
                                    <select className={fieldClass} {...bind("billing")}>
                                        {billingTypes.map((billing) => (
                                            <option key={billing}>{billing}</option>
                                        ))}
                                    </select>
                                </Field>
                            </div>

                            <Field label="Quotation PDF *">
                                <input
                                    required
                                    type="file"
                                    accept=".pdf,application/pdf"
                                    onChange={(event) =>
                                        setFile(event.target.files?.[0] || null)
                                    }
                                    className="block w-full text-xs text-slate-800 file:mr-4 file:cursor-pointer file:rounded-lg file:border-0 file:bg-teal-900 file:px-4 file:py-2.5 file:font-semibold file:text-white"
                                />
                            </Field>

                            <p className="text-xs leading-6 text-slate-700">
                                Maximum 10 MB. PDF details are entered manually.
                                For mixed billing, the uploaded PDF remains the reference.
                            </p>
                        </div>
                    ) : (
                        <>
                            <div className="flex items-center justify-between gap-4">
                                <h3 className="text-sm font-bold text-slate-950">
                                    Products & services
                                </h3>
                                <Button
                                    variant="secondary"
                                    onClick={() => setItems((current) => [...current, newItem()])}
                                >
                                    <Plus size={15} /> Add item
                                </Button>
                            </div>

                            <div className="space-y-4">
                                {items.map((item, index) => (
                                    <div
                                        key={item.id}
                                        className="rounded-xl border border-slate-200 bg-slate-50 p-4"
                                    >
                                        <div className="mb-3 flex items-center justify-between">
                                            <strong className="text-xs text-slate-800">
                                                Item {index + 1}
                                            </strong>
                                            <IconButton
                                                aria-label={`Remove item ${index + 1}`}
                                                disabled={items.length === 1}
                                                onClick={() =>
                                                    setItems((current) =>
                                                        current.filter((row) => row.id !== item.id)
                                                    )
                                                }
                                            >
                                                <Trash2 size={16} />
                                            </IconButton>
                                        </div>

                                        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
                                            <Field label="Description *">
                                                <input
                                                    required
                                                    maxLength={200}
                                                    value={item.description}
                                                    className={fieldClass}
                                                    onChange={(event) =>
                                                        updateItem(item.id, "description", event.target.value)
                                                    }
                                                />
                                            </Field>

                                            <Field label="Billing">
                                                <select
                                                    value={item.billing}
                                                    className={fieldClass}
                                                    onChange={(event) =>
                                                        updateItem(item.id, "billing", event.target.value)
                                                    }
                                                >
                                                    {billingTypes.map((billing) => (
                                                        <option key={billing}>{billing}</option>
                                                    ))}
                                                </select>
                                            </Field>

                                            <Field label="Quantity *">
                                                <input
                                                    required
                                                    type="number"
                                                    min="0.01"
                                                    step="0.01"
                                                    value={item.quantity}
                                                    className={fieldClass}
                                                    onChange={(event) =>
                                                        updateItem(item.id, "quantity", event.target.value)
                                                    }
                                                />
                                            </Field>

                                            <Field label="Unit rate *">
                                                <input
                                                    required
                                                    type="number"
                                                    min="0"
                                                    step="0.01"
                                                    value={item.rate}
                                                    className={fieldClass}
                                                    onChange={(event) =>
                                                        updateItem(item.id, "rate", event.target.value)
                                                    }
                                                />
                                            </Field>
                                        </div>
                                    </div>
                                ))}
                            </div>

                            <div className="max-w-xs">
                                <Field label="Applicable tax — %">
                                    <input
                                        required
                                        type="number"
                                        min="0"
                                        max="100"
                                        step="0.01"
                                        className={fieldClass}
                                        {...bind("tax")}
                                    />
                                </Field>
                            </div>

                            <div className="grid gap-3 sm:grid-cols-3">
                                {billingTypes.map((billing) => (
                                    <div
                                        key={billing}
                                        className="rounded-xl border border-teal-100 bg-teal-50 p-4"
                                    >
                                        <p className="text-xs font-medium text-teal-900">
                                            {billing} total
                                        </p>
                                        <strong className="mt-2 block text-lg text-teal-950">
                                            {money(totals[billing].total, form.currency)}
                                        </strong>
                                        <small className="mt-1 block text-[11px] text-slate-700">
                                            Including entered tax
                                        </small>
                                    </div>
                                ))}
                            </div>

                            <Field label="Payment, delivery & warranty terms">
                                <textarea
                                    rows={4}
                                    maxLength={2000}
                                    className={`${fieldClass} resize-y`}
                                    {...bind("terms")}
                                />
                            </Field>
                        </>
                    )}

                    {error && (
                        <p
                            role="alert"
                            className="rounded-lg bg-rose-50 p-3 text-sm text-rose-900"
                        >
                            {error}
                        </p>
                    )}

                    <footer className="flex justify-end gap-3 border-t border-slate-200 pt-5">
                        <Button variant="secondary" onClick={onClose}>
                            Cancel
                        </Button>
                        <Button type="submit">
                            <Save size={16} />
                            {busy
                                ? "Saving..."
                                : isUpload
                                    ? "Save quotation"
                                    : "Generate & save PDF"}
                        </Button>
                    </footer>
                </fieldset>
            </form>
        </QuoteDialog>
    );
}
