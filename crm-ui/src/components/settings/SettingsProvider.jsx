import { useCallback, useEffect, useState } from "react";
import { SettingsContext } from "../../context/SettingsContext";
import { getSettings } from "../../services/settingsApi";
import { getUsers } from "../../services/usersApi";
import { runtimeSettings, setRuntimeSettings } from "../../lib/runtimeSettings";
import { Button } from "../ui";

export default function SettingsProvider({ user, onProfileUpdated, onLogout, children }) {
  const [state, setState] = useState(null);
  const [attempt, setAttempt] = useState(0);
  const accept = useCallback((settings) => {
    const previousDivision = runtimeSettings().workspace.defaultDivision;
    const previousName = runtimeSettings().profile.name;
    setRuntimeSettings(settings);
    if (previousDivision !== settings.workspace.defaultDivision) window.dispatchEvent(new CustomEvent("crm:default-division-changed", { detail: settings.workspace.defaultDivision }));
    if (previousName !== settings.profile.name) window.dispatchEvent(new Event("crm:users-updated"));
    setState({ settings });
    onProfileUpdated?.({ name: settings.profile.name, version: settings.versions.profile });
  }, [onProfileUpdated]);
  useEffect(() => {
    let active = true;
    const refreshRoster = () => getUsers().then((directory) => { if (active) setRuntimeSettings(runtimeSettings(), directory.users.filter((account) => account.isActive).map((account) => account.name)); }).catch(() => {});
    window.addEventListener("crm:users-updated", refreshRoster);
    Promise.all([getSettings(), getUsers()]).then(([settings, directory]) => {
      if (active) { setRuntimeSettings(settings, directory.users.filter((account) => account.isActive).map((account) => account.name)); setState({ settings }); }
    }).catch((error) => { if (active) setState({ error: error.message }); });
    return () => { active = false; window.removeEventListener("crm:users-updated", refreshRoster); };
  }, [user.id, attempt]);
  if (!state?.settings) return <div className="flex min-h-dvh items-center justify-center bg-[#f4f7f5] p-5 text-sm text-slate-900"><div className="max-w-md space-y-4">{state?.error ? <><p role="alert">{state.error}</p><Button onClick={() => setAttempt((value) => value + 1)}>Retry workspace settings</Button><Button variant="secondary" onClick={() => onLogout?.()}>Sign out</Button></> : <p role="status">Loading your workspace preferences...</p>}</div></div>;
  return <SettingsContext.Provider value={{ settings: state.settings, accept, user }}>{children}</SettingsContext.Provider>;
}
