function openDatabase() {
    return new Promise((resolve, reject) => {
        const request = indexedDB.open("engen-crm", 1);

        request.onupgradeneeded = () => {
            const store = request.result.createObjectStore("quotations", {
                keyPath: "id",
            });

            store.createIndex("divisionNumber", ["division", "number"], {
                unique: true,
            });
        };

        request.onsuccess = () => resolve(request.result);
        request.onerror = () => reject(request.error);
        request.onblocked = () =>
            reject(new Error("Close other CRM tabs and try again."));
    });
}

export async function getQuotations() {
    const database = await openDatabase();

    return new Promise((resolve, reject) => {
        const transaction = database.transaction("quotations", "readonly");
        const request = transaction.objectStore("quotations").getAll();

        transaction.oncomplete = () => {
            database.close();
            resolve(request.result);
        };

        transaction.onabort = () => {
            database.close();
            reject(transaction.error || new Error("Could not load quotations."));
        };

        transaction.onerror = () => {
            // The transaction abort handler reports the error.
        };
    });
}

export async function saveQuotation(quotation) {
    const database = await openDatabase();

    return new Promise((resolve, reject) => {
        const transaction = database.transaction("quotations", "readwrite");

        transaction.objectStore("quotations").put(quotation);

        transaction.oncomplete = () => {
            database.close();
            resolve(quotation);
        };

        transaction.onabort = () => {
            database.close();

            reject(
                new Error(
                    transaction.error?.name === "ConstraintError"
                        ? "This quotation number already exists in this division."
                        : "Could not save. Browser storage may be full or unavailable."
                )
            );
        };

        transaction.onerror = () => {
            // The transaction abort handler reports the error.
        };
    });
}