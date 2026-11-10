import { useRef, useState } from "react";
import { Plus, Save, Trash2 } from "lucide-react";
import { divisionLabel, divisions } from "../data/crm";
import { useSettings } from "../context/SettingsContext";
import { customerFormPayload } from "../lib/customerForm.js";
import Modal from "./Modal";
import ReferralFields from "./ReferralFields";
import { Button, IconButton } from "./ui";

const inputClass = "min-w-0 w-full rounded-lg border border-slate-300 bg-white px-3 py-2.5 text-base text-slate-950 outline-none placeholder:text-slate-500 focus:border-teal-600 focus:ring-2 focus:ring-teal-100 sm:text-sm";
const emptyContact = () => ({ name: "", designation: "", phone: "", email: "" });

function Field({ label, children, wide = false }) {
  return <label className={`flex min-w-0 flex-col gap-2 text-xs font-semibold text-slate-800 ${wide ? "sm:col-span-2" : ""}`}>{label}{children}</label>;
}

export default function CustomerForm({ customer, onSave, onClose }) {
  const { user } = useSettings();
  const [form, setForm] = useState(() => Object.fromEntries(["name", "type", "address", "city", "state", "postcode", "gst", "notes"].map((key) => [key, customer?.[key] || (key === "type" ? "Company" : "")])));
  const [contacts, setContacts] = useState(() => customer?.contacts?.length ? customer.contacts.map((contact) => ({ ...contact })) : [emptyContact()]);
  const [selectedDivisions, setSelectedDivisions] = useState(customer?.divisions || []);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const lock = useRef(false);
  function bind(key) { return { value: form[key], onChange: (event) => setForm((current) => ({ ...current, [key]: event.target.value })) }; }
  function updateContact(index, key, value) { setContacts((current) => current.map((item, i) => i === index ? { ...item, [key]: value } : item)); }
  async function submit(event) {
    event.preventDefault();
    if (lock.current) return;
    let payload;
    try { payload = customerFormPayload({ customer, form, contacts, selectedDivisions, referral: new FormData(event.currentTarget), userName: user.name }); }
    catch (failure) { setError(failure.message); return; }
    lock.current = true; setSaving(true); setError("");
    try { await onSave(payload); }
    catch (failure) { setError(failure.message || "Unable to save customer."); }
    finally { lock.current = false; setSaving(false); }
  }
  return <Modal title={customer ? "Edit customer" : "Add customer"} onClose={() => { if (!lock.current) onClose(); }}>
    <form onSubmit={submit}><fieldset disabled={saving} className="min-w-0">
      <div className="space-y-5 p-4 sm:p-5">
        <div className="grid gap-4 sm:grid-cols-2">
          <Field label="Customer / company name *"><input required autoFocus maxLength={120} className={inputClass} {...bind("name")} /></Field>
          <Field label="Customer type"><select className={inputClass} {...bind("type")}><option>Company</option><option>Individual</option></select></Field>
        </div>
        <fieldset><legend className="mb-3 text-xs font-semibold text-slate-800">Associated divisions *</legend><div className="flex flex-wrap gap-2">{divisions.map((division) => <label key={division} className="flex cursor-pointer items-center gap-2 rounded-lg border border-slate-300 px-3 py-2 text-xs font-semibold text-slate-800"><input type="checkbox" checked={selectedDivisions.includes(division)} onChange={() => setSelectedDivisions((current) => current.includes(division) ? current.filter((value) => value !== division) : [...current, division])} className="accent-teal-800" />{divisionLabel(division)}</label>)}</div></fieldset>
        <section className="space-y-3"><div className="flex flex-wrap items-center justify-between gap-2"><h3 className="text-sm font-bold">Contact persons</h3><Button variant="secondary" onClick={() => setContacts((current) => [...current, emptyContact()])}><Plus size={15} />Add contact</Button></div>
          {contacts.map((contact, index) => <div key={index} className="rounded-xl border border-slate-200 bg-slate-50 p-3 shadow-sm"><div className="mb-3 flex items-center justify-between gap-2"><h4 className="text-xs font-semibold">{index === 0 ? "Primary contact" : `Contact ${index + 1}`}</h4>{index > 0 && <IconButton aria-label={`Remove contact ${index + 1}`} onClick={() => setContacts((current) => current.filter((_, i) => i !== index))}><Trash2 size={15} /></IconButton>}</div><div className="grid gap-3 sm:grid-cols-2">{[["name", "Name", 120, "text"], ["designation", "Designation", 120, "text"], ["phone", "Phone", 30, "tel"], ["email", "Email", 254, "email"]].map(([key, label, maxLength, type]) => <Field key={key} label={label}><input type={type} maxLength={maxLength} className={inputClass} value={contact[key] || ""} onChange={(event) => updateContact(index, key, event.target.value)} /></Field>)}</div></div>)}
          <p className="text-xs leading-5 text-slate-600">Enter a phone number or email for the primary contact.</p>
        </section>
        <div className="grid gap-4 sm:grid-cols-2"><Field label="Address" wide><textarea rows={3} maxLength={500} className={`${inputClass} resize-y`} {...bind("address")} /></Field>{[["city", "City", 100], ["state", "State", 100], ["postcode", "Postal code", 20], ["gst", "GST number", 30]].map(([key, label, maxLength]) => <Field key={key} label={label}><input maxLength={maxLength} className={inputClass} {...bind(key)} /></Field>)}</div>
        <p className="text-xs leading-6 text-slate-700">New profiles are assigned to you. Administrators can change record access in Settings → Users &amp; access.</p>
        <ReferralFields initialSource={customer?.leadSource || "Direct Enquiry"} initialReference={customer?.referredBy || null} initialNotes={customer?.referenceNotes || ""} />
        <Field label="Notes"><textarea rows={3} maxLength={10000} className={`${inputClass} resize-y`} {...bind("notes")} /></Field>
        {error && <p role="alert" className="rounded-lg bg-rose-50 p-3 text-xs leading-6 text-rose-900">{error}</p>}
      </div>
      <footer className="flex flex-wrap justify-end gap-2 border-t border-slate-200 p-4"><Button variant="secondary" onClick={onClose}>Cancel</Button><Button type="submit"><Save size={16} />{saving ? "Saving..." : "Save customer"}</Button></footer>
    </fieldset></form>
  </Modal>;
}
