import { useCallback, useEffect, useRef, useState } from "react";
import { LogIn, Eye, EyeOff, LockKeyhole } from "lucide-react";
import { login, logout, restoreSession } from "../../services/authApi";
import { Button } from "../ui";
import { ForgotPassword, ResetPassword } from "./PasswordRecovery";
import { consumeResetLink } from "../../lib/resetLink";

// Consume once before React StrictMode runs initializers twice; never persist this token.
const initialResetLink = consumeResetLink();

export default function AuthGate({ children }) {
  const [session, setSession] = useState({ checking: true, user: null, error: "" });
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [busy, setBusy] = useState(false);
  const lock = useRef(false);
  const [resetLink, setResetLink] = useState(initialResetLink);
  const [recovering, setRecovering] = useState(false);
  const [notice, setNotice] = useState("");
  const updateProfile = useCallback((changes) => setSession((current) => current.user ? { ...current, user: { ...current.user, ...changes } } : current), []);

  useEffect(() => {
    const capture = () => { const link = consumeResetLink(); if (link) { setResetLink(link); setRecovering(false); } };
    window.addEventListener("hashchange", capture);
    return () => window.removeEventListener("hashchange", capture);
  }, []);

  useEffect(() => {
    if (resetLink) return;
    let active = true;
    const expired = () => { if (active) setSession({ checking: false, user: null, error: "" }); };
    window.addEventListener("crm:session-expired", expired);
    restoreSession().then((user) => { if (active) setSession({ checking: false, user, error: "" }); })
      .catch((error) => { if (active) setSession({ checking: false, user: null, error: error.status === 401 ? "" : error.message }); });
    return () => { active = false; window.removeEventListener("crm:session-expired", expired); };
  }, [resetLink]);

  async function submit(event) {
    event.preventDefault();
    if (lock.current) return;
    lock.current = true; setBusy(true);
    try {
      const user = await login(email, password);
      setPassword(""); setSession({ checking: false, user, error: "" });
    } catch (error) { setSession({ checking: false, user: null, error: error.status === 401 ? "Email or password is incorrect, or the account is inactive." : error.message }); }
    finally { lock.current = false; setBusy(false); }
  }

  async function signOut(allDevices = false) {
    if (lock.current) return;
    lock.current = true; setBusy(true);
    try { await logout(allDevices); setSession({ checking: false, user: null, error: "" }); }
    catch (error) { setSession((current) => ({ ...current, error: `Sign out failed. ${error.message}` })); }
    finally { lock.current = false; setBusy(false); }
  }

  if (resetLink) return <ResetPassword link={resetLink} onComplete={() => { setResetLink(null); setRecovering(false); setSession({ checking: false, user: null, error: "" }); setNotice("Password reset. Sign in with your new password."); }} onRequestNew={() => { setResetLink(null); setRecovering(true); }} onBack={() => setResetLink(null)} />;
  if (recovering) return <ForgotPassword initialEmail={email} onBack={() => setRecovering(false)} onComplete={() => { setRecovering(false); setSession({ checking: false, user: null, error: "" }); setNotice("Password reset. Sign in with your new password."); }} />;
  if (session.checking) return <div role="status" className="flex min-h-dvh items-center justify-center bg-[#f4f7f5] p-5 text-sm font-medium text-slate-800">Checking your session...</div>;
  if (session.user) return <>{session.error && <p role="alert" className="bg-rose-50 px-4 py-3 text-sm text-rose-900">{session.error}</p>}{children({ user: session.user, onLogout: signOut, signingOut: busy, onProfileUpdated: updateProfile })}</>;

  return <main className="flex min-h-dvh items-center justify-center bg-[#f4f7f5] px-4 py-8 font-sans text-slate-950">
    <section className="w-full max-w-md rounded-2xl border border-slate-200 bg-white p-6 shadow-xl shadow-teal-950/5 sm:p-8">
      <img src={`${import.meta.env.BASE_URL}Engen%20logo%20Final.png`} alt="ENGEN - Scaling Heights" className="mb-7 h-20 w-44 object-contain" />
      <div className="mb-5"><span className="mb-3 inline-flex rounded-xl bg-teal-50 p-3 text-teal-800"><LockKeyhole size={22} /></span><h1 className="text-2xl font-bold tracking-tight">Sign in to your workspace</h1><p className="mt-2 text-sm leading-6 text-slate-700">Manage your leads, customers and quotations with ENGEN CRM.</p></div>
      {notice && <p role="status" className="mb-4 rounded-lg bg-teal-50 p-3 text-xs text-teal-950">{notice}</p>}
      <form onSubmit={submit} className="space-y-4"><fieldset disabled={busy} className="min-w-0 space-y-4">
        <label className="block text-xs font-semibold text-slate-800">Email address<input type="email" required maxLength={254} autoComplete="username" value={email} onChange={(event) => setEmail(event.target.value)} className="mt-2 min-h-11 w-full rounded-lg border border-slate-300 px-3 text-sm text-slate-950 outline-none focus:border-teal-600 focus:ring-2 focus:ring-teal-100" /></label>
        <label className="block text-xs font-semibold text-slate-800">Password<div className="relative mt-2"><input type={showPassword ? "text" : "password"} required maxLength={128} autoComplete="current-password" value={password} onChange={(event) => setPassword(event.target.value)} className="min-h-11 w-full rounded-lg border border-slate-300 py-2 pr-12 pl-3 text-sm text-slate-950 outline-none focus:border-teal-600 focus:ring-2 focus:ring-teal-100" /><button type="button" aria-label={showPassword ? "Hide password" : "Show password"} aria-pressed={showPassword} onClick={() => setShowPassword((value) => !value)} className="absolute inset-y-0 right-0 flex w-11 items-center justify-center rounded-r-lg text-slate-600 hover:text-teal-800 focus-visible:outline-2 focus-visible:outline-teal-700">{showPassword ? <EyeOff size={18} /> : <Eye size={18} />}</button></div></label>
        {session.error && <p role="alert" className="rounded-lg bg-rose-50 p-3 text-xs leading-5 text-rose-900">{session.error}</p>}
        <Button type="submit" className="w-full"><LogIn size={17} />{busy ? "Signing in..." : "Sign in"}</Button>
        <button type="button" onClick={() => { setRecovering(true); setNotice(""); }} className="min-h-10 w-full text-xs font-semibold text-teal-800 hover:underline">Forgot password?</button>
      </fieldset></form>
      <p className="mt-5 text-xs leading-5 text-slate-600">Need an account or help signing in? Contact your workspace administrator.</p>
    </section>
  </main>;
}
