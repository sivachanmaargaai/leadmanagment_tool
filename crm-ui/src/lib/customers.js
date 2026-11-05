const STORAGE_KEY = "engen-crm-customers";

export function normalise(value = "") {
    return value.trim().replace(/\s+/g, " ").toLowerCase();
}

export function belongsToCustomer(record, customer) {
    if (record.customerId) return record.customerId === customer.id;

    return [customer.name, ...(customer.aliases || [])].some(
        (name) => normalise(name) === normalise(record.customer)
    );
}

export function readCustomers() {
    const raw = localStorage.getItem(STORAGE_KEY);
    const records = raw ? JSON.parse(raw) : [];

    if (
        !Array.isArray(records) ||
        records.some((record) => !record.id || !record.name)
    ) {
        throw new Error("Saved customer data could not be read.");
    }

    return records;
}

export function saveCustomer(customer) {
    const records = readCustomers();
    const exists = records.some((record) => record.id === customer.id);

    const updated = exists
        ? records.map((record) =>
            record.id === customer.id ? customer : record
        )
        : [customer, ...records];

    localStorage.setItem(STORAGE_KEY, JSON.stringify(updated));
    return updated;
}

export function buildCustomerDirectory(saved, leads, quotations) {
    const directory = saved.map((customer) => ({
        ...customer,
        divisions: [...(customer.divisions || [])],
    }));

    // Existing enquiries/documents become discoverable customer profiles.
    for (const record of [...leads, ...quotations]) {
        if (!record.customer?.trim()) continue;

        let customer = directory.find((entry) =>
            belongsToCustomer(record, entry)
        );

        if (!customer) {
            customer = {
                id: record.customerId || `customer-${record.id}`,
                name: record.customer.trim(),
                type: "Company",
                contacts: [
                    {
                        name: record.contact || "",
                        designation: "",
                        phone: record.phone || "",
                        email: record.email || "",
                    },
                ],
                address: record.address || "",
                city: "",
                state: "",
                postcode: "",
                gst: "",
                assignedTo: "Admin",
                notes: "",
                divisions: [],
                aliases: [],
                leadSource: record.leadSource || "",
                referredBy: record.referredBy || null,
                referenceNotes: record.referenceNotes || "",
                history: [],
            };

            directory.push(customer);
        }

        if (
            record.division &&
            !customer.divisions.includes(record.division)
        ) {
            customer.divisions.push(record.division);
        }
    }

    return directory.map((customer) => {
        const linkedLeads = leads.filter((lead) =>
            belongsToCustomer(lead, customer)
        );

        return {
            ...customer,
            stage: linkedLeads.some((lead) => lead.status === "Won")
                ? "Converted Customer"
                : "Prospect",
            leadCount: linkedLeads.length,
        };
    });
}