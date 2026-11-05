import { useRef, useState } from "react";
import { changePassword } from "../../services/settingsApi";
import { Button, Card, CardHeading } from "../ui";

export default function PasswordChange() {
  const [form, setForm] = useState({ current: "", password: "", confirm: "" });
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const lock = useRef(false);
  async function submit(event) {
    event.preventDefault();
    if (lock.current) return;
    if (form.password !== form.confirm) { setError("New passwords do not match."); return; }
    lock.current = true; setBusy(true); setError("");
    try { await changePassword(form.current, form.password); }
    catch (failure) { setError(failure.message); }
    finally { lock.current = false; setBusy(false); }
  }
  return <Card><CardHeading title="Change password" description="Use 8–128 characters. Changing your password signs you out on all devices." /><form onSubmit={submit}><fieldset disabled={busy} className="space-y-4 px-4 pb-4 sm:px-5 sm:pb-5">
    {[["current", "Current password", "current-password"], ["password", "New password", "new-password"], ["confirm", "Confirm new password", "new-password"]].map(([key, label, autoComplete]) => <label key={key} className="block text-xs font-semibold text-slate-800">{label}<input type="password" required minLength={key === "current" ? 1 : 8} maxLength={128} autoComplete={autoComplete} value={form[key]} onChange={(event) => setForm({ ...form, [key]: event.target.value })} className="mt-2 min-h-10 w-full rounded-lg border border-slate-300 px-3 text-sm text-slate-950 outline-none focus:border-teal-600" /></label>)}
    {error && <p role="alert" className="rounded-lg bg-rose-50 p-3 text-xs text-rose-900">{error}</p>}<Button type="submit">{busy ? "Changing password..." : "Change password & sign out"}</Button>
  </fieldset></form></Card>;
}
