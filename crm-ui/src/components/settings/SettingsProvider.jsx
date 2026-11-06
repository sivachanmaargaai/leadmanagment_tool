import { useCallback, useEffect, useRef, useState } from "react";
import { SettingsContext } from "../../context/SettingsContext";
import { getSettings } from "../../services/settingsApi";
import { getUsers } from "../../services/usersApi";
import { runtimeSettings, setRuntimeSettings } from "../../lib/runtimeSettings";
import { Button } from "../ui";

export default function SettingsProvider({ user, onProfileUpdated, onLogout, children }) {
  const [state, setState] = useState(null);
  const [attempt, setAttempt] = useState(0);
  const initialLoad = useRef(null);
  const accept = useCallback((settings) => {
    const previousDivision = runtimeSettings().workspace.defaultDivision;
    const previousName = runtimeSettings().profile.name;
    setRuntimeSettings(settings);
    if (previousDivision !== settings.workspace.defaultDivision) window.dispatchEvent(new CustomEvent("crm:default-division-changed", { detail: settings.workspace.defaultDivision }));
    if (previousName !== settings.profile.name) window.dispatchEvent(new Event("crm:users-updated"));
    setState({ settings });
    onProfileUpdated?.({ name: settings.profile.name, version: settings.versions.profile, ...(typeof settings.canAccessQuotations === "boolean" ? { canAccessQuotations: settings.canAccessQuotations } : {}) });
  }, [onProfileUpdated]);
  useEffect(() => {
    let active = true;
    setRuntimeSettings(runtimeSettings(), []);
    const refreshRoster = () => getUsers().then((directory) => { if (active) setRuntimeSettings(runtimeSettings(), directory.users.filter((account) => account.isActive).map((account) => account.name)); }).catch(() => {});
    window.addEventListener("crm:users-updated", refreshRoster);
    // StrictMode replays effects in development. Share only this provider's
    // in-flight startup reads; retries and a different user get new requests.
    if (initialLoad.current?.userId !== user.id || initialLoad.current?.attempt !== attempt) {
      initialLoad.current = { userId: user.id, attempt, settings: getSettings(), roster: getUsers() };
    }
    initialLoad.current.settings.then((settings) => {
      if (active) { setRuntimeSettings(settings); setState({ settings }); }
    }).catch((error) => { if (active) setState({ error: error.message }); });
    // Staff labels enhance pickers but must not block opening the workspace.
    initialLoad.current.roster.then((directory) => {
      if (active) setRuntimeSettings(runtimeSettings(), directory.users.filter((account) => account.isActive).map((account) => account.name));
    }).catch(() => {});
    return () => { active = false; window.removeEventListener("crm:users-updated", refreshRoster); };
  }, [user.id, attempt]);
  if (!state?.settings) return <div className="flex min-h-dvh items-center justify-center bg-[#f4f7f5] p-5 text-sm text-slate-900"><div className="max-w-md space-y-4">{state?.error ? <><p role="alert">{state.error}</p><Button onClick={() => setAttempt((value) => value + 1)}>Retry workspace settings</Button><Button variant="secondary" onClick={() => onLogout?.()}>Sign out</Button></> : <p role="status">Loading your workspace preferences...</p>}</div></div>;
  return <SettingsContext.Provider value={{ settings: state.settings, accept, user }}>{children}</SettingsContext.Provider>;
}
