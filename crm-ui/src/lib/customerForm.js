export function customerFormPayload({ customer, form, contacts, selectedDivisions, referral, userName }) {
  const fields = Object.fromEntries(Object.entries(form).map(([key, value]) => [key, String(value).trim()]));
  const cleanedContacts = contacts.map((contact) => Object.fromEntries(["name", "designation", "phone", "email"].map((key) => [key, String(contact[key] || "").trim()])));
  if (!fields.name) throw new Error("Enter the customer name.");
  if (!selectedDivisions.length) throw new Error("Select at least one division.");
  if (!cleanedContacts[0]?.phone && !cleanedContacts[0]?.email) throw new Error("Enter a primary phone number or email address.");
  const leadSource = String(referral.get("leadSource") || "Direct Enquiry");
  const needsReference = ["Referral", "Known Network"].includes(leadSource);
  const referenceId = String(referral.get("referredById") || "");
  if (needsReference && !referenceId) throw new Error("Select or add a reference contact.");
  const renamed = customer?.name && customer.name.trim() !== fields.name;
  const aliases = [...new Set([...(customer?.aliases || []), ...(renamed ? [customer.name] : [])])];
  const history = [...(customer?.history || []), { id: crypto.randomUUID(), at: new Date().toISOString(), message: customer ? renamed ? `Customer renamed from ${customer.name} to ${fields.name}.` : "Customer profile updated." : "Customer profile created." }];
  return { ...fields, ...(customer?.id ? { id: customer.id, ...(customer.version ? { version: customer.version } : {}) } : {}), contacts: cleanedContacts, divisions: [...selectedDivisions], assignedTo: customer?.assignedTo || userName,
    leadSource, referredBy: needsReference ? { id: referenceId, ...Object.fromEntries(["name", "company", "phone", "email"].map((key) => [key, String(referral.get(`referredBy${key[0].toUpperCase()}${key.slice(1)}`) || "")])) } : null,
    referenceNotes: needsReference ? String(referral.get("referenceNotes") || "").trim() : "", aliases, history };
}
