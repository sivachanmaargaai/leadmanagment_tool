import { createContext, useContext } from "react";
export const SettingsContext = createContext(null);
export function useSettings() { return useContext(SettingsContext); }
