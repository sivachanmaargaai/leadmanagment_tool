import RecordPicker from "./RecordPicker";

export default function CustomerField({ customerId, customer, onChange, maxLength = 120 }) {
  return <div className="min-w-0 space-y-2">
    <input aria-label="Customer / company name" name="customer" required maxLength={maxLength} value={customer} onChange={(event) => onChange({ customer: event.target.value, customerId: null })} placeholder="Customer / company name" className="w-full rounded-lg border border-slate-300 bg-white px-3 py-2.5 text-sm font-normal text-slate-950 outline-none focus:border-teal-600 focus:ring-2 focus:ring-teal-100" />
    <RecordPicker value={customerId} name={customer} onChange={(profile) => onChange({ customer: profile.name, customerId: profile.id })} />
    {!customerId && <p className="text-[11px] font-normal text-slate-600">Unlinked enquiry. Select an existing profile to connect its activity.</p>}
  </div>;
}
