import { useState } from "react";

export default function useBrowserStorage(key, fallback) {
    const [state, setState] = useState(() => {
        try {
            const raw = localStorage.getItem(key);
            const value = raw ? JSON.parse(raw) : fallback;

            if (Array.isArray(fallback) && !Array.isArray(value)) {
                throw new Error("Invalid saved data.");
            }

            return { value, error: "" };
        } catch {
            return {
                value: fallback,
                error: "Saved data could not be loaded. Please check browser storage.",
            };
        }
    });

    function save(next) {
        try {
            const value =
                typeof next === "function" ? next(state.value) : next;

            localStorage.setItem(key, JSON.stringify(value));
            setState({ value, error: "" });
            return true;
        } catch {
            setState((current) => ({
                ...current,
                error: "Could not save. Browser storage may be unavailable or full.",
            }));
            return false;
        }
    }

    return [state.value, save, state.error];
}