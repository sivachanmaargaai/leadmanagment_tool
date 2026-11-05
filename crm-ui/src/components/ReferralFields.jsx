import { useState } from "react";
import { Plus, UserRoundPlus, X } from "lucide-react";
import { Button } from "./ui";
import { runtimeSettings } from "../lib/runtimeSettings";
import { useSettings } from "../context/SettingsContext";
import { readReferenceContacts, saveReferenceContacts } from "../lib/referenceContacts.js";

const inputClass = "w-full rounded-lg border border-slate-300 bg-white px-3 py-2.5 text-sm text-slate-950 outline-none placeholder:text-slate-500 focus:border-teal-600 focus:ring-2 focus:ring-teal-100";
const emptyContact = { name: "", company: "", phone: "", email: "" };

export default function ReferralFields({
  initialSource = "Direct Enquiry",
  initialReference = null,
  initialNotes = "",
}) {
  const { user } = useSettings();
  const sources = [...new Set(["Direct Enquiry", "Referral", "Known Network", ...runtimeSettings().leads.sources, "Other", initialSource])];
  const [source, setSource] = useState(initialSource);
  const [contacts, setContacts] = useState(() => {
    const saved = readReferenceContacts(user.id);
    return initialReference && !saved.some((contact) => contact.id === initialReference.id)
      ? [...saved, initialReference]
      : saved;
  });
  const [selectedId, setSelectedId] = useState(initialReference?.id || "");
  const [search, setSearch] = useState("");
  const [adding, setAdding] = useState(false);
  const [draft, setDraft] = useState(emptyContact);
  const [error, setError] = useState("");
  const needsReference = ["Referral", "Known Network"].includes(source);
  const selectedContact = contacts.find((contact) => contact.id === selectedId);
  const filteredContacts = contacts.filter((contact) =>
    [contact.name, contact.company, contact.phone, contact.email].filter(Boolean).join(" ").toLowerCase().includes(search.trim().toLowerCase())
  );
  const visibleContacts = selectedContact && !filteredContacts.some((contact) => contact.id === selectedId)
    ? [selectedContact, ...filteredContacts]
    : filteredContacts;

  function updateDraft(field, value) {
    setDraft((current) => ({ ...current, [field]: value }));
    setError("");
  }

  function saveContact() {
    const contact = {
      id: crypto.randomUUID(),
      name: draft.name.trim(),
      company: draft.company.trim(),
      phone: draft.phone.trim(),
      email: draft.email.trim(),
    };
    if (!contact.name) {
      setError("Enter the reference person's name.");
      return;
    }
    if (contact.email && !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(contact.email)) {
      setError("Enter a valid email address.");
      return;
    }
    const normalisePhone = (value) => String(value || "").replace(/[^\d+]/g, "");
    const duplicate = contacts.find((entry) =>
      (contact.email && entry.email?.toLowerCase() === contact.email.toLowerCase()) ||
      (normalisePhone(contact.phone) && normalisePhone(entry.phone) === normalisePhone(contact.phone))
    );
    if (duplicate) {
      setSelectedId(duplicate.id);
      setAdding(false);
      setSearch("");
      setDraft(emptyContact);
      setError("");
      return;
    }
    try {
      // Read the latest registry so another open tab's contacts are retained.
      const updated = [...readReferenceContacts(user.id), contact];
      saveReferenceContacts(user.id, updated);
      setContacts(updated);
      setSelectedId(contact.id);
      setAdding(false);
      setSearch("");
      setDraft(emptyContact);
      setError("");
    } catch {
      setError("Could not save. Browser storage may be unavailable.");
    }
  }

  return (
    <section className="space-y-4 rounded-xl border border-teal-200 bg-teal-50/40 p-4 sm:col-span-2">
      <div className="flex items-center gap-2">
        <UserRoundPlus size={18} className="text-teal-800" />
        <h3 className="text-sm font-bold text-slate-950">Lead source & reference</h3>
      </div>
      <label className="block">
        <span className="mb-2 block text-xs font-semibold text-slate-800">Lead source *</span>
        <select name="leadSource" value={source} className={inputClass} onChange={(event) => {
          setSource(event.target.value);
          setError("");
          setAdding(false);
        }}>
          {sources.map((name) => <option key={name}>{name}</option>)}
        </select>
      </label>
      {needsReference && <>
        <label className="block">
          <span className="mb-2 block text-xs font-semibold text-slate-800">Search reference contacts</span>
          <input type="search" placeholder="Name, company, phone or email..." value={search} onChange={(event) => setSearch(event.target.value)} className={inputClass} />
        </label>
        <label className="block">
          <span className="mb-2 block text-xs font-semibold text-slate-800">Referred by *</span>
          <select name="referredById" value={selectedId} onChange={(event) => setSelectedId(event.target.value)} required className={inputClass}>
            <option value="">Select a reference contact</option>
            {visibleContacts.map((contact) => <option key={contact.id} value={contact.id}>
              {contact.name}{contact.company ? ` — ${contact.company}` : ""}
            </option>)}
          </select>
        </label>
        {selectedContact && <div className="rounded-lg border border-teal-200 bg-white p-3">
          <strong className="text-xs text-teal-950">{selectedContact.name}</strong>
          <p className="mt-1 break-words text-xs leading-6 text-slate-700">
            {[selectedContact.company, selectedContact.phone, selectedContact.email].filter(Boolean).join(" · ") || "No additional contact details"}
          </p>
        </div>}
        {!adding ? <Button variant="secondary" onClick={() => { setAdding(true); setError(""); }}>
          <Plus size={15} /> Add reference contact
        </Button> : <div className="space-y-4 rounded-xl border border-slate-200 bg-white p-4">
          <div className="flex items-center justify-between">
            <strong className="text-sm text-slate-950">New reference contact</strong>
            <button type="button" aria-label="Close reference contact fields" onClick={() => { setAdding(false); setError(""); }} className="rounded-md p-1 text-slate-700 hover:bg-slate-100">
              <X size={17} />
            </button>
          </div>
          <div className="grid gap-4 sm:grid-cols-2">
            {[["name", "Name *"], ["company", "Company"], ["phone", "Phone"], ["email", "Email"]].map(([field, label]) => <label key={field} className="block">
              <span className="mb-2 block text-xs font-semibold text-slate-800">{label}</span>
              <input type={field === "phone" ? "tel" : "text"} value={draft[field]} maxLength={field === "phone" ? 30 : 120} onChange={(event) => updateDraft(field, event.target.value)} className={inputClass} />
            </label>)}
          </div>
          <p className="text-xs leading-5 text-slate-700">Save this contact, then create the lead.</p>
          <Button onClick={saveContact}><Plus size={15} /> Save contact</Button>
        </div>}
        <label className="block">
          <span className="mb-2 block text-xs font-semibold text-slate-800">Reference notes</span>
          <textarea name="referenceNotes" defaultValue={initialNotes} placeholder="How do we know this person? Any introduction details?" rows={3} maxLength={500} className={`${inputClass} resize-y`} />
        </label>
        <input type="hidden" name="referredByName" value={selectedContact?.name || ""} />
        <input type="hidden" name="referredByCompany" value={selectedContact?.company || ""} />
        <input type="hidden" name="referredByPhone" value={selectedContact?.phone || ""} />
        <input type="hidden" name="referredByEmail" value={selectedContact?.email || ""} />
      </>}
      {error && <p role="alert" className="text-xs font-medium text-rose-800">{error}</p>}
    </section>
  );
}
