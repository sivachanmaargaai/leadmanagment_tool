
export const billingTypes = ["One-time", "Monthly", "Yearly"];

export const quoteStatuses = [
    "Draft",
    "Sent",
    "Accepted",
    "Rejected",
    "Expired",
];

const round = (value) => Math.round((value + Number.EPSILON) * 100) / 100;

export function today() {
    return new Intl.DateTimeFormat("en-CA", {
        timeZone: "Asia/Kolkata",
        year: "numeric",
        month: "2-digit",
        day: "2-digit",
    }).format(new Date());
}

export function money(value, currency = "INR") {
    return new Intl.NumberFormat("en-IN", {
        style: "currency",
        currency,
        maximumFractionDigits: 2,
    }).format(value);
}

export function calculateTotals(items, taxPercent = 0) {
    return Object.fromEntries(
        billingTypes.map((billing) => {
            const subtotal = round(
                items
                    .filter((item) => item.billing === billing)
                    .reduce(
                        (sum, item) =>
                            sum + round(Number(item.quantity) * Number(item.rate)),
                        0
                    )
            );

            const tax = round((subtotal * Number(taxPercent)) / 100);

            return [billing, { subtotal, tax, total: round(subtotal + tax) }];
        })
    );
}

export function effectiveStatus(quotation) {
    if (
        quotation.status === "Sent" &&
        quotation.validUntil &&
        quotation.validUntil < today()
    ) {
        return "Expired";
    }

    return quotation.status;
}

export async function validatePdf(file) {
    if (!file) throw new Error("Select a PDF file.");

    if (file.size > 10 * 1024 * 1024) {
        throw new Error("Select a PDF smaller than 10 MB.");
    }

    const header = new TextDecoder().decode(
        await file.slice(0, 5).arrayBuffer()
    );

    if (header !== "%PDF-") {
        throw new Error("This file is not a recognised PDF.");
    }
}

export function safeFilename(value) {
    return String(value).replace(/[^a-z0-9._-]/gi, "-") || "quotation";
}

export function downloadPdf(version) {
    const url = URL.createObjectURL(version.file);
    const anchor = document.createElement("a");

    anchor.href = url;
    anchor.download = version.name;
    document.body.appendChild(anchor);
    anchor.click();
    anchor.remove();

    setTimeout(() => URL.revokeObjectURL(url), 1000);
}

