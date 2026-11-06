import { useEffect, useRef, useState } from "react";
import { Plus, Pencil, ShieldCheck, Users } from "lucide-react";
import { createUser, getUsers, updateUser } from "../../services/usersApi";
import { Avatar, Button, Card, CardHeading, EmptyState, IconButton } from "../ui";
import Modal from "../Modal";

const fieldClass = "mt-1.5 block min-h-10 w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-slate-950 outline-none focus:border-teal-600 focus:ring-2 focus:ring-teal-100";

function AccountForm({ account, adminCount, onSave, onClose }) {
  const [form, setForm] = useState({ name: account?.name || "", email: account?.email || "", role: account?.role || "Staff", isActive: account?.isActive ?? true, password: "", confirmPassword: "" });
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const lock = useRef(false);
  const adminAvailable = adminCount < 2 || account?.role === "Admin";
  function bind(key) { return { value: form[key], onChange: (event) => setForm((current) => ({ ...current, [key]: event.target.value })) }; }
  async function submit(event) {
    event.preventDefault();
    if (lock.current) return;
    if (form.password !== form.confirmPassword) { setError("Passwords do not match."); return; }
    lock.current = true; setBusy(true); setError("");
    try { await onSave(form); } catch (failure) { setError(failure.message); }
    finally { lock.current = false; setBusy(false); }
  }
  return <Modal title={account ? "Edit login account" : "Create login account"} onClose={busy ? () => {} : onClose}>
    <form onSubmit={submit}><fieldset disabled={busy} className="min-w-0 space-y-4 p-4 sm:p-5">
      <div className="grid gap-4 sm:grid-cols-2"><label className="text-xs font-semibold text-slate-800">Name<input required maxLength={120} autoComplete="name" className={fieldClass} {...bind("name")} /></label><label className="text-xs font-semibold text-slate-800">Email<input required type="email" maxLength={254} autoComplete="off" className={fieldClass} {...bind("email")} /></label></div>
      <label className="block text-xs font-semibold text-slate-800">Role<select className={fieldClass} {...bind("role")}><option>Staff</option><option disabled={!adminAvailable}>Admin</option></select></label>
      {!adminAvailable && <p className="text-xs leading-5 text-slate-600">Both Admin slots are used. New accounts can be Staff only until the second administrator is demoted.</p>}
      <div className="grid gap-4 sm:grid-cols-2"><label className="text-xs font-semibold text-slate-800">{account ? "New password (optional)" : "Password"}<input type="password" required={!account} minLength={8} maxLength={128} autoComplete="new-password" className={fieldClass} {...bind("password")} /></label><label className="text-xs font-semibold text-slate-800">Confirm password<input type="password" required={!account || Boolean(form.password)} minLength={8} maxLength={128} autoComplete="new-password" className={fieldClass} {...bind("confirmPassword")} /></label></div>
      <p className="text-xs leading-5 text-slate-600">Passwords require 8–128 characters and are stored securely. Existing passwords cannot be viewed.</p>
      {account && <label className="flex min-h-10 items-center gap-2 text-xs font-semibold text-slate-800"><input type="checkbox" checked={form.isActive} onChange={(event) => setForm({ ...form, isActive: event.target.checked })} className="size-4 accent-teal-800" />Account active</label>}
      {account && <p className="text-xs leading-5 text-slate-600">Changing email, role, password or active status signs this account out of existing sessions.</p>}
      {error && <p role="alert" className="rounded-lg bg-rose-50 p-3 text-xs leading-5 text-rose-900">{error}</p>}
      <div className="flex flex-wrap justify-end gap-2 border-t border-slate-100 pt-4"><Button variant="secondary" onClick={onClose}>Cancel</Button><Button type="submit">{busy ? "Saving..." : account ? "Save account" : "Create account"}</Button></div>
    </fieldset></form>
  </Modal>;
}

export default function UserManagement({ currentUser }) {
  const [reload, setReload] = useState(0);
  const [result, setResult] = useState(null);
  const [editor, setEditor] = useState(null);
  const [notice, setNotice] = useState("");
  const [search, setSearch] = useState("");
  const current = result?.key === reload ? result : null;
  const directory = current?.data;
  useEffect(() => {
    let active = true;
    getUsers().then((data) => { if (active) setResult({ key: reload, data }); })
      .catch((error) => { if (active) setResult({ key: reload, error: error.message }); });
    return () => { active = false; };
  }, [reload]);
  async function save(form) {
    if (editor.account) await updateUser(editor.account, form);
    else await createUser(form);
    setNotice(editor.account ? "Login account updated." : "Login account created. The user can now sign in with their email and password.");
    setEditor(null); setReload((value) => value + 1);
    window.dispatchEvent(new Event("crm:users-updated"));
  }
  const users = (directory?.users || []).filter((account) => `${account.name} ${account.email} ${account.role}`.toLowerCase().includes(search.trim().toLowerCase()));
  return <Card>
    <CardHeading title="Users & access" description="Real login accounts and workspace access.">{directory?.canManageUsers && <Button onClick={() => setEditor({ account: null })}><Plus size={16} />Add login account</Button>}</CardHeading>
    {!current ? <p role="status" className="p-6 text-sm text-slate-700">Loading login accounts...</p> : current.error ? <div role="alert" className="space-y-3 p-4 text-sm text-rose-900"><p>{current.error}</p><Button variant="secondary" onClick={() => setReload((value) => value + 1)}>Reload users</Button></div> : <div className="space-y-4 px-4 pb-4 sm:px-5 sm:pb-5">
      <div className="rounded-xl border border-teal-100 bg-teal-50 p-3 text-xs leading-6 text-teal-950"><div className="flex items-start gap-2"><ShieldCheck size={17} className="mt-1 shrink-0" /><p>{directory.canManageUsers ? <>You are the Owner (first administrator). Only you can create accounts, edit users and change roles. <strong>{directory.adminCount}/{directory.adminLimit} Admin slots used.</strong> Inactive administrators still use a slot.</> : directory.scope === "Staff only" ? "Only the Owner can manage accounts. As the second administrator, you can view staff accounts here. Common role permissions are managed in Roles & permissions." : "Only the Owner can manage accounts. Your login profile is shown below."}</p></div></div>
      {notice && <p role="status" className="rounded-lg bg-teal-50 p-3 text-xs leading-5 text-teal-950">{notice}</p>}

      <div className="flex flex-wrap items-center justify-between gap-2"><label className="min-w-0 flex-1 text-xs font-semibold text-slate-700">Search accounts<input value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Name, email or role" className={`${fieldClass} sm:max-w-sm`} /></label><Button variant="secondary" onClick={() => setReload((value) => value + 1)}>Reload users</Button></div>
      <div className="space-y-3">{users.length ? users.map((account) => <article key={account.id} className="grid min-w-0 grid-cols-[36px_minmax(0,1fr)] items-center gap-x-3 gap-y-2 rounded-xl border border-slate-200 bg-white p-3 shadow-sm sm:grid-cols-[36px_minmax(0,1fr)_auto] sm:p-4">
        <Avatar name={account.name} /><div className="min-w-0 flex-1"><strong className="block break-words text-sm text-slate-950">{account.name}{account.id === currentUser?.id && <span className="ml-2 text-[10px] font-medium text-slate-600">You</span>}</strong><p className="mt-1 break-all text-xs text-slate-700">{account.email}</p><p className="mt-1 text-[10px] text-slate-500">Created {new Date(account.createdAt).toLocaleDateString("en-IN", { timeZone: "Asia/Kolkata" })}</p></div>
        <div className="col-start-2 flex min-w-0 flex-wrap items-center gap-2 sm:col-start-auto"><span className={`rounded-md px-2 py-1 text-[10px] font-semibold ${account.isOwner ? "bg-lime-100 text-teal-950" : "bg-teal-50 text-teal-900"}`}>{account.isOwner ? "Owner · Admin" : account.role}</span><span className={`rounded-md px-2 py-1 text-[10px] font-semibold ${account.isActive ? "bg-emerald-50 text-emerald-900" : "bg-slate-100 text-slate-700"}`}>{account.isActive ? "Active" : "Inactive"}</span>{directory.canManageUsers && !account.isOwner && <IconButton aria-label={`Edit ${account.name}`} title="Edit login account" onClick={() => setEditor({ account })}><Pencil size={17} /></IconButton>}</div>
      </article>) : <EmptyState icon={Users} title="No accounts found" description="Adjust your search or ask the Owner to create staff accounts." />}</div>
      <p className="text-[11px] leading-5 text-slate-600">Account changes save immediately. Module access is managed for the whole Staff role in Roles & permissions. The Owner account is protected from edits and deactivation.</p>
    </div>}
    {editor && directory?.canManageUsers && <AccountForm account={editor.account} adminCount={directory.adminCount} onSave={save} onClose={() => setEditor(null)} />}
  </Card>;
}
