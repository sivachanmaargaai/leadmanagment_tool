import { useEffect, useRef, useState } from "react";
import { ArrowLeft, KeyRound, Mail } from "lucide-react";
import { forgotPassword, resetPassword, verifyRecoveryOtp } from "../../services/authApi";
import { Button } from "../ui";

const field = "mt-2 min-h-11 w-full rounded-lg border border-slate-300 px-3 text-sm text-slate-950 outline-none focus:border-teal-600 focus:ring-2 focus:ring-teal-100";

function RecoveryCard({ title, description, children }) {
  return <main className="flex min-h-dvh items-center justify-center bg-[#f4f7f5] px-4 py-8 font-sans text-slate-950"><section className="w-full max-w-md rounded-2xl border border-slate-200 bg-white p-6 shadow-xl shadow-teal-950/5 sm:p-8"><img src={`${import.meta.env.BASE_URL}Engen%20logo%20Final.png`} alt="ENGEN - Scaling Heights" className="mb-6 h-20 w-44 object-contain" /><h1 className="text-2xl font-bold tracking-tight">{title}</h1><p className="mt-2 mb-5 text-sm leading-6 text-slate-700">{description}</p>{children}</section></main>;
}

export function ForgotPassword({ initialEmail = "", onBack, onComplete }) {
  const [email, setEmail] = useState(initialEmail);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [challenge, setChallenge] = useState(null);
  const [code, setCode] = useState("");
  const [grant, setGrant] = useState(null);
  const [resendAt, setResendAt] = useState(0);
  const [seconds, setSeconds] = useState(0);
  const lock = useRef(false);
  useEffect(() => {
    if (!resendAt) return;
    const tick = () => setSeconds(Math.max(0, Math.ceil((resendAt - Date.now()) / 1000)));
    tick();
    const timer = setInterval(tick, 1000);
    return () => clearInterval(timer);
  }, [resendAt]);
  async function submit(event) {
    event?.preventDefault();
    if (lock.current) return;
    lock.current = true; setBusy(true); setError(""); setMessage("");
    try {
      const result = await forgotPassword(email);
      setChallenge(result.challengeId); setCode("");
      setMessage(`${result.message} The code expires in ${result.expiresInMinutes} minutes.`);
      setSeconds(result.resendAfterSeconds); setResendAt(Date.now() + result.resendAfterSeconds * 1000);
    }
    catch (failure) {
      setError(failure.message);
      if (failure.status === 429 && failure.retryAfter) {
        setSeconds(failure.retryAfter); setResendAt(Date.now() + failure.retryAfter * 1000);
      }
    }
    finally { lock.current = false; setBusy(false); }
  }
  async function verify(event) {
    event.preventDefault();
    if (lock.current) return;
    lock.current = true; setBusy(true); setError("");
    try {
      const result = await verifyRecoveryOtp(challenge, code);
      setGrant(result.resetToken); setCode(""); setChallenge(null);
    } catch (failure) { setError(failure.message); }
    finally { lock.current = false; setBusy(false); }
  }
  function requestNew() { setGrant(null); setChallenge(null); setCode(""); setError(""); setMessage(""); }
  if (grant) return <ResetPassword link={{ valid: true, token: grant }} onComplete={onComplete} onRequestNew={requestNew} onBack={onBack} />;
  return <RecoveryCard title={challenge ? "Enter your reset code" : "Forgot your password?"} description={challenge ? `Enter the 6-digit code sent to ${email.trim()}.` : "Enter the email address you use to sign in. We'll send a reset code if an active account matches."}>
    <form onSubmit={challenge ? verify : submit}><fieldset disabled={busy} className="min-w-0 space-y-4">
      {challenge ? <label className="block text-xs font-semibold text-slate-800">Reset code<input type="text" inputMode="numeric" pattern="[0-9]{6}" required minLength={6} maxLength={6} autoComplete="one-time-code" autoFocus value={code} onChange={(event) => setCode(event.target.value.replace(/[^0-9]/g, ""))} className={`${field} tracking-[0.4em]`} /></label> : <label className="block text-xs font-semibold text-slate-800">Email address<input type="email" required maxLength={254} autoComplete="username" value={email} onChange={(event) => setEmail(event.target.value)} className={field} /></label>}
      {error && <p role="alert" className="rounded-lg bg-rose-50 p-3 text-xs leading-5 text-rose-900">{error}</p>}
      {message && <p role="status" className="rounded-lg bg-teal-50 p-3 text-xs leading-6 text-teal-950">{message}</p>}
      <Button type="submit" disabled={!challenge && seconds > 0} className="w-full"><Mail size={17} />{busy ? "Please wait..." : challenge ? "Verify code" : "Send reset code"}</Button>
    </fieldset></form>
    {challenge && <div className="mt-3 flex flex-wrap gap-3"><button type="button" disabled={busy || seconds > 0} onClick={() => submit()} className="min-h-11 text-sm font-semibold text-teal-800 disabled:text-slate-500">{seconds > 0 ? `Resend in ${seconds}s` : "Resend code"}</button><button type="button" disabled={busy} onClick={requestNew} className="min-h-11 text-sm font-semibold text-teal-800">Change email</button></div>}
    {!challenge && seconds > 0 && <p role="status" className="mt-3 text-xs text-slate-700">You can request another code in {seconds}s.</p>}
    <Button variant="secondary" className="mt-4 w-full" disabled={busy} onClick={onBack}><ArrowLeft size={16} />Back to sign in</Button>
    <p className="mt-4 text-xs leading-5 text-slate-600">Check your spam folder too. Never share your code. A new code replaces your previous code.</p>
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
    {!link.valid ? <div className="space-y-4"><p role="alert" className="text-sm text-rose-900">This password reset authorization is invalid or incomplete. Request a new code.</p><Button onClick={onRequestNew}>Request a new code</Button></div> : <form onSubmit={submit}><fieldset disabled={busy} className="min-w-0 space-y-4">
      <label className="block text-xs font-semibold text-slate-800">New password<input type="password" required minLength={8} maxLength={128} autoComplete="new-password" value={password} onChange={(event) => setPassword(event.target.value)} className={field} /></label>
      <label className="block text-xs font-semibold text-slate-800">Confirm new password<input type="password" required minLength={8} maxLength={128} autoComplete="new-password" value={confirm} onChange={(event) => setConfirm(event.target.value)} className={field} /></label>
      {error && <div role="alert" className="rounded-lg bg-rose-50 p-3 text-xs leading-5 text-rose-900"><p>{error}</p><button type="button" onClick={onRequestNew} className="mt-2 min-h-10 font-semibold underline">Request a new code</button></div>}
      <Button type="submit" className="w-full"><KeyRound size={17} />{busy ? "Resetting password..." : "Reset password"}</Button>
    </fieldset></form>}
    <Button variant="secondary" className="mt-4 w-full" disabled={busy} onClick={onBack}>Back to sign in</Button>
  </RecoveryCard>;
}
