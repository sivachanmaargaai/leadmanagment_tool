import { useRef, useState } from "react";
import { ArrowLeft, KeyRound, Mail } from "lucide-react";
import { forgotPassword, resetPassword } from "../../services/authApi";
import { Button } from "../ui";

const field = "mt-2 min-h-11 w-full rounded-lg border border-slate-300 px-3 text-sm text-slate-950 outline-none focus:border-teal-600 focus:ring-2 focus:ring-teal-100";

function RecoveryCard({ title, description, children }) {
  return <main className="flex min-h-dvh items-center justify-center bg-[#f4f7f5] px-4 py-8 font-sans text-slate-950"><section className="w-full max-w-md rounded-2xl border border-slate-200 bg-white p-6 shadow-xl shadow-teal-950/5 sm:p-8"><img src={`${import.meta.env.BASE_URL}Engen%20logo%20Final.png`} alt="ENGEN - Scaling Heights" className="mb-6 h-20 w-44 object-contain" /><h1 className="text-2xl font-bold tracking-tight">{title}</h1><p className="mt-2 mb-5 text-sm leading-6 text-slate-700">{description}</p>{children}</section></main>;
}

export function ForgotPassword({ initialEmail = "", onBack }) {
  const [email, setEmail] = useState(initialEmail);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const lock = useRef(false);
  async function submit(event) {
    event.preventDefault();
    if (lock.current) return;
    lock.current = true; setBusy(true); setError(""); setMessage("");
    try { const result = await forgotPassword(email); setMessage(`${result.message} The link expires in ${result.expiresInMinutes} minutes.`); }
    catch (failure) { setError(failure.message); }
    finally { lock.current = false; setBusy(false); }
  }
  return <RecoveryCard title="Forgot your password?" description="Enter the email address you use to sign in. We'll send a secure reset link if an active account matches.">
    <form onSubmit={submit}><fieldset disabled={busy} className="space-y-4"><label className="block text-xs font-semibold text-slate-800">Email address<input type="email" required maxLength={254} autoComplete="username" value={email} onChange={(event) => setEmail(event.target.value)} className={field} /></label>
      {error && <p role="alert" className="rounded-lg bg-rose-50 p-3 text-xs leading-5 text-rose-900">{error}</p>}
      {message && <p role="status" className="rounded-lg bg-teal-50 p-3 text-xs leading-6 text-teal-950">{message}</p>}
      <Button type="submit" className="w-full"><Mail size={17} />{busy ? "Requesting link..." : "Send reset link"}</Button>
    </fieldset></form><Button variant="secondary" className="mt-4 w-full" disabled={busy} onClick={onBack}><ArrowLeft size={16} />Back to sign in</Button>
    <p className="mt-4 text-xs leading-5 text-slate-600">Check your spam folder too. Please wait a minute before requesting another link.</p>
  </RecoveryCard>;
}

export function ResetPassword({ link, onComplete, onRequestNew, onBack }) {
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const lock = useRef(false);
  async function submit(event) {
    event.preventDefault();
    if (lock.current) return;
    if (password !== confirm) { setError("Passwords do not match."); return; }
    lock.current = true; setBusy(true); setError("");
    try { await resetPassword(link.token, password); setPassword(""); setConfirm(""); onComplete(); }
    catch (failure) { setError(failure.message); }
    finally { lock.current = false; setBusy(false); }
  }
  return <RecoveryCard title="Choose a new password" description="Use 8–128 characters. After resetting, sign in again. Existing sessions on all devices will be signed out.">
    {!link.valid ? <div className="space-y-4"><p role="alert" className="text-sm text-rose-900">This reset link is invalid or incomplete. Request a new link.</p><Button onClick={onRequestNew}>Request a new link</Button></div> : <form onSubmit={submit}><fieldset disabled={busy} className="space-y-4">
      <label className="block text-xs font-semibold text-slate-800">New password<input type="password" required minLength={8} maxLength={128} autoComplete="new-password" value={password} onChange={(event) => setPassword(event.target.value)} className={field} /></label>
      <label className="block text-xs font-semibold text-slate-800">Confirm new password<input type="password" required minLength={8} maxLength={128} autoComplete="new-password" value={confirm} onChange={(event) => setConfirm(event.target.value)} className={field} /></label>
      {error && <div role="alert" className="rounded-lg bg-rose-50 p-3 text-xs leading-5 text-rose-900"><p>{error}</p><button type="button" onClick={onRequestNew} className="mt-2 min-h-10 font-semibold underline">Request a new link</button></div>}
      <Button type="submit" className="w-full"><KeyRound size={17} />{busy ? "Resetting password..." : "Reset password"}</Button>
    </fieldset></form>}
    <Button variant="secondary" className="mt-4 w-full" disabled={busy} onClick={onBack}>Back to sign in</Button>
  </RecoveryCard>;
}
