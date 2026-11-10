import { useRef, useState } from "react";
import { canAccessQuotations } from "../lib/permissions";
import RolePermissions from "../components/settings/RolePermissions";
import PasswordChange from "../components/settings/PasswordChange";
import OperationsPanel from "../components/settings/OperationsPanel";
import { useSettings } from "../context/SettingsContext";
import { defaultSettings } from "../lib/runtimeSettings";
import { getSettings, saveSettings as persistSettings } from "../services/settingsApi";
import CrmAssignments from "../components/settings/CrmAssignments";
import UserManagement from "../components/settings/UserManagement";
import {
    UserRound,
    Building2,
    Users,
    ShieldCheck,
    SlidersHorizontal,
    FileText,
    Bell,
    PanelsTopLeft,
    Save,
    Check,
} from "lucide-react";
import { Button, Card } from "../components/ui";
import { divisionLabel, divisions } from "../data/crm";

const tabs = [
    { id: "profile", label: "My profile", icon: UserRound },
    { id: "company", label: "Company & divisions", icon: Building2 },
    { id: "users", label: "Users & access", icon: Users },
    { id: "permissions", label: "Roles & permissions", icon: ShieldCheck },
    { id: "leads", label: "Lead settings", icon: SlidersHorizontal },
    { id: "quotation", label: "Products & quotations", icon: FileText },
    { id: "notifications", label: "Notifications", icon: Bell },
    { id: "workspace", label: "Workspace", icon: PanelsTopLeft },
];

const defaults = defaultSettings();

const inputClass =
    "min-w-0 w-full rounded-lg border border-slate-300 bg-white px-3 py-2.5 text-sm text-slate-950 outline-none transition placeholder:text-slate-500 focus:border-teal-600 focus:ring-2 focus:ring-teal-100";

function Field({ label, hint, className = "", ...props }) {
    return (
        <label className={`block min-w-0 ${className}`}>
            <span className="mb-2 block text-xs font-semibold text-slate-800">
                {label}
            </span>
            <input className={inputClass} {...props} />
            {hint && (
                <span className="mt-2 block text-xs leading-5 text-slate-600">
                    {hint}
                </span>
            )}
        </label>
    );
}

function Select({ label, options, ...props }) {
    return (
        <label className="block min-w-0">
            <span className="mb-2 block text-xs font-semibold text-slate-800">
                {label}
            </span>
            <select className={inputClass} {...props}>
                {options.map((option) => (
                    <option key={option} value={option}>{divisionLabel(option)}</option>
                ))}
            </select>
        </label>
    );
}

function TextArea({ label, ...props }) {
    return (
        <label className="block min-w-0">
            <span className="mb-2 block text-xs font-semibold text-slate-800">
                {label}
            </span>
            <textarea
                className={`${inputClass} resize-y`}
                rows={3}
                {...props}
            />
        </label>
    );
}

function Toggle({ label, description, checked, onChange, disabled }) {
    return (
        <div className="flex items-center justify-between gap-5 border-b border-slate-100 py-4 last:border-0">
            <div>
                <strong className="block text-sm font-semibold text-slate-900">
                    {label}
                </strong>
                {description && (
                    <p className="mt-1 text-xs leading-5 text-slate-600">
                        {description}
                    </p>
                )}
            </div>

            <button
                type="button"
                role="switch"
                disabled={disabled}
                aria-checked={checked}
                aria-label={label}
                onClick={() => onChange(!checked)}
                className={`inline-flex h-6 w-11 shrink-0 items-center rounded-full p-1 transition-colors focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-teal-700 ${checked ? "bg-teal-800" : "bg-slate-300"
                    }`}
            >
                <span
                    className={`size-4 rounded-full bg-white shadow-sm transition-transform ${checked ? "translate-x-5" : "translate-x-0"
                        }`}
                />
            </button>
        </div>
    );
}

function Section({ title, description, children }) {
    return (
        <div>
            <h2 className="text-lg font-bold text-slate-950">{title}</h2>
            <p className="mb-4 mt-1.5 text-xs leading-5 text-slate-700">
                {description}
            </p>
            {children}
        </div>
    );
}

export default function Settings({ user }) {
    const { settings, accept } = useSettings();
    // The authenticated provider already loaded these. Preserve versions for CAS;
    // the existing Reload saved settings action explicitly fetches fresh values.
    return <SettingsEditor user={user} initialSettings={settings} onSaved={accept} />;
}

function SettingsEditor({ user, initialSettings, onSaved }) {
    const visibleTabs = tabs.filter(({ id }) => (id !== "quotation" || canAccessQuotations(user)) && (id !== "permissions" || user.role === "Admin"));
    const [tab, setTab] = useState("profile");
    const [settings, setSettings] = useState(() => structuredClone(initialSettings));
    const [selectedDivision, setSelectedDivision] = useState(divisions[0]);
    const [notice, setNotice] = useState("");

    const [saving, setSaving] = useState(false);
    const [saveError, setSaveError] = useState("");
    const saveLock = useRef(false);
    const sharedSections = ["company", "divisions", "leads", "quotation"];

    function update(section, field, value) {
        setSettings((current) => ({
            ...current,
            [section]: { ...current[section], [field]: value },
        }));
        setNotice("");
    }

    function bind(section, field) {
        return {
            value: section === "leads" && field === "sources" && Array.isArray(settings.leads.sources) ? settings.leads.sources.join(", ") : settings[section][field],
            disabled: saving || (sharedSections.includes(section) && !settings.canManageShared),
            onChange: (event) => update(section, field, event.target.value),
        };
    }

    function toggle(section, field) {
        return {
            checked: settings[section][field],
            disabled: saving || (sharedSections.includes(section) && !settings.canManageShared),
            onChange: (value) => update(section, field, value),
        };
    }

    function updateDivision(field, value) {
        setSettings((current) => ({
            ...current,
            divisions: {
                ...current.divisions,
                [selectedDivision]: {
                    ...current.divisions[selectedDivision],
                    [field]: value,
                },
            },
        }));
        setNotice("");
    }

    async function saveSettings(event) {
        event.preventDefault();
        if (saveLock.current) return;
        saveLock.current = true; setSaving(true); setSaveError(""); setNotice("");
        try {
            const saved = await persistSettings(settings);
            setSettings(saved); onSaved(saved); setNotice("Settings saved to your workspace.");
        } catch (error) { setSaveError(error.message); }
        finally { saveLock.current = false; setSaving(false); }
    }

    async function reloadSaved() {
        if (saveLock.current) return;
        saveLock.current = true; setSaving(true); setSaveError("");
        try { const saved = await getSettings(); setSettings(saved); onSaved(saved); setNotice("Saved settings reloaded."); }
        catch (error) { setSaveError(error.message); }
        finally { saveLock.current = false; setSaving(false); }
    }

    const divisionSettings = {
        ...defaults.divisions[selectedDivision],
        ...settings.divisions[selectedDivision],
    };

    return (
        <div className="grid w-full min-w-0 grid-cols-1 items-start gap-4 lg:grid-cols-[224px_minmax(0,1fr)]">
            {/* Settings navigation */}
            <Card className="w-full min-w-0 p-2 lg:sticky lg:top-4">
                <p className="px-3 pb-3 pt-2 text-[10px] font-bold tracking-widest text-slate-600">
                    SETTINGS
                </p>

                <label className="block lg:hidden">
                    <span className="sr-only">Settings section</span>
                    <select value={tab} disabled={saving} onChange={(event) => { setTab(event.target.value); setNotice(""); }} className="min-h-11 w-full min-w-0 rounded-lg border border-slate-300 bg-white px-3 text-sm font-semibold text-slate-900 outline-none focus:border-teal-600 focus:ring-2 focus:ring-teal-100">
                        {visibleTabs.map(({ id, label }) => <option key={id} value={id}>{label}</option>)}
                    </select>
                </label>
                <nav className="hidden space-y-1 lg:block" aria-label="Settings sections">
                    {visibleTabs.map(({ id, label, icon: Icon }) => (
                        <button
                            key={id}
                            disabled={saving}
                            type="button"
                            aria-current={tab === id ? "page" : undefined}
                            onClick={() => {
                                setTab(id);
                                setNotice("");
                            }}
                            className={`flex shrink-0 items-center gap-2 whitespace-nowrap rounded-xl px-3 py-2.5 text-left text-xs lg:w-full lg:whitespace-normal font-semibold transition-colors focus-visible:outline-2 focus-visible:outline-teal-700 ${tab === id
                                ? "bg-teal-900 text-white"
                                : "text-slate-700 hover:bg-teal-50 hover:text-teal-950"
                                }`}
                        >
                            <Icon size={17} className="shrink-0" />
                            <span className="min-w-0">{label}</span>
                        </button>
                    ))}
                </nav>
            </Card>

            {/* Settings content */}
            <div className="w-full min-w-0 space-y-4">
            {tab === "users" ? <><UserManagement currentUser={user} />{user.role === "Admin" && <CrmAssignments />}</> : tab === "permissions" && user.role === "Admin" ? <RolePermissions /> : (
            <><Card className="overflow-hidden">
                <form onSubmit={saveSettings}>
                    <div className="border-b border-amber-200 bg-amber-50 px-5 py-3 text-xs leading-6 text-amber-950">
                        Signed in as {settings.profile.email}. Your preferences follow your login.
                        Company, division and business defaults can be changed only by the Owner.
                    </div>

                    <fieldset disabled={saving} className="min-w-0 border-0 p-4 sm:p-5">
                        {tab === "profile" && (
                            <Section
                                title="My profile"
                                description="Your contact details and workspace identity."
                            >
                                <div className="grid gap-4 sm:grid-cols-2">
                                    <Field label="Full name" {...bind("profile", "name")} />
                                    <Field
                                        label="Email address"
                                        type="email"
                                        readOnly hint="Login email is managed through Users & access."
                                        {...bind("profile", "email")}
                                    />
                                    <Field
                                        label="Phone number"
                                        type="tel"
                                        {...bind("profile", "phone")}
                                    />
                                    <Field
                                        label="Designation"
                                        {...bind("profile", "designation")}
                                    />
                                </div>


                            </Section>
                        )}

                        {tab === "company" && (
                            <Section
                                title="Company & divisions"
                                description="Manage parent company details and division-specific quotation information."
                            >
                                <div className="mb-4 flex flex-wrap items-center gap-4 rounded-xl border border-slate-200 p-4">
                                    <img
                                        src={`${import.meta.env.BASE_URL}Engen%20logo%20Final.png`}
                                        alt="ENGEN"
                                        className="h-auto w-32 object-contain"
                                    />
                                    <p className="text-xs leading-6 text-slate-700">
                                        Current workspace logo
                                        <br />
                                        ENGEN · Scaling Heights
                                    </p>
                                </div>

                                <div className="grid gap-4 sm:grid-cols-2">
                                    <Field label="Company name" {...bind("company", "name")} />
                                    <Field label="Website" {...bind("company", "website")} />
                                    <Field
                                        label="Company email"
                                        type="email"
                                        {...bind("company", "email")}
                                    />
                                    <Field
                                        label="Phone"
                                        type="tel"
                                        {...bind("company", "phone")}
                                    />
                                    <Field
                                        label="GST number"
                                        {...bind("company", "gst")}
                                        className="sm:col-span-2"
                                    />
                                </div>

                                <div className="mt-5">
                                    <TextArea
                                        label="Company address"
                                        {...bind("company", "address")}
                                    />
                                </div>

                                <div className="mt-8 border-t border-slate-200 pt-6">
                                    <h3 className="mb-5 text-sm font-bold text-slate-950">
                                        Division details
                                    </h3>

                                    <Select
                                        label="Select division"
                                        options={divisions}
                                        value={selectedDivision}
                                        onChange={(event) =>
                                            setSelectedDivision(event.target.value)
                                        }
                                    />

                                    <div className="mt-5 grid gap-4 sm:grid-cols-2">
                                        <Field
                                            label="GST number"
                                            disabled={!settings.canManageShared} value={divisionSettings.gst}
                                            onChange={(event) =>
                                                updateDivision("gst", event.target.value)
                                            }
                                        />
                                        <Field
                                            label="Quotation prefix"
                                            disabled={!settings.canManageShared} value={divisionSettings.prefix}
                                            onChange={(event) =>
                                                updateDivision("prefix", event.target.value)
                                            }
                                        />
                                    </div>

                                    <div className="mt-5">
                                        <TextArea
                                            label="Division address"
                                            disabled={!settings.canManageShared} value={divisionSettings.address}
                                            onChange={(event) =>
                                                updateDivision("address", event.target.value)
                                            }
                                        />
                                    </div>
                                </div>
                            </Section>
                        )}

                        {tab === "leads" && (
                            <Section
                                title="Lead settings"
                                description="Set defaults and information requirements for new leads."
                            >
                                <div className="grid gap-4 sm:grid-cols-2">
                                    <Select
                                        label="Default priority"
                                        options={["High", "Medium", "Low"]}
                                        {...bind("leads", "defaultPriority")}
                                    />
                                    <Select
                                        label="Default status"
                                        options={["New", "In Progress", "Follow-up"]}
                                        {...bind("leads", "defaultStatus")}
                                    />
                                    <Field
                                        label="Suggested new follow-up interval — days"
                                        type="number"
                                        min="1"
                                        {...bind("leads", "followUpDays")}
                                    />
                                </div>

                                <div className="my-5">
                                    <TextArea
                                        label="Lead sources — separated by commas"
                                        {...bind("leads", "sources")}
                                    />
                                </div>

                                <Toggle
                                    label="Require customer contact"
                                    description="A contact person or contact details must be provided on new leads."
                                    {...toggle("leads", "requireContact")}
                                />
                                <Toggle
                                    label="Require requirement description"
                                    description="Include a brief description of the enquiry."
                                    {...toggle("leads", "requireDescription")}
                                />
                            </Section>
                        )}

                        {tab === "quotation" && (
                            <Section
                                title="Products & quotations"
                                description="Defaults for embedded / IoT products, software and service quotations."
                            >
                                <div className="grid gap-4 sm:grid-cols-2">
                                    <Field
                                        label="Fallback quotation prefix"
                                        {...bind("quotation", "prefix")}
                                    />
                                    <Field
                                        label="Next quotation number"
                                        type="number"
                                        min="1"
                                        {...bind("quotation", "nextNumber")}
                                    />
                                    <Select
                                        label="Currency"
                                        options={["INR", "USD", "EUR", "GBP"]}
                                        {...bind("quotation", "currency")}
                                    />
                                    <Field
                                        label="Validity — days"
                                        type="number"
                                        min="1"
                                        {...bind("quotation", "validity")}
                                    />
                                    <Field
                                        label="Default tax — %"
                                        type="number"
                                        min="0"
                                        max="100"
                                        step="0.01"
                                        placeholder="Set applicable tax"
                                        {...bind("quotation", "tax")}
                                    />
                                </div>

                                <div className="mt-5 space-y-5">
                                    <TextArea
                                        label="Payment terms"
                                        placeholder="Enter your standard payment terms"
                                        {...bind("quotation", "paymentTerms")}
                                    />
                                    <TextArea
                                        label="Warranty / support terms"
                                        {...bind("quotation", "warranty")}
                                    />
                                    <TextArea
                                        label="Default quotation notes"
                                        {...bind("quotation", "notes")}
                                    />
                                </div>

                                <div className="mt-5">
                                    <Toggle
                                        label="Show company logo"
                                        description="Include ENGEN branding in the quotation."
                                        {...toggle("quotation", "showLogo")}
                                    />
                                    <Toggle
                                        label="Show signature area"
                                        {...toggle("quotation", "showSignature")}
                                    />
                                    <Toggle
                                        label="Require Owner approval"
                                        description="Only the Owner can mark quotations as Sent or Accepted."
                                        {...toggle("quotation", "approvalRequired")}
                                    />
                                </div>

                                <p className="mt-5 rounded-lg bg-teal-50 p-4 text-xs leading-6 text-teal-950">
                                    These defaults apply to new quotations. Existing PDF revisions retain their original company details and formatting.
                                </p>
                            </Section>
                        )}

                        {tab === "notifications" && (
                            <Section
                                title="Notifications"
                                description="Choose which in-app reminders your workspace should use."
                            >
                                <Toggle
                                    label="High-priority lead alerts"
                                    description="High-priority leads that are still open."
                                    {...toggle("notifications", "leadPriority")}
                                />
                                <Toggle
                                    label="Follow-up reminders"
                                    description="Before a scheduled customer follow-up."
                                    {...toggle("notifications", "followUp")}
                                />
                                <Toggle
                                    label="Overdue follow-ups"
                                    description="When a pending follow-up passes its due time."
                                    {...toggle("notifications", "overdue")}
                                />
                                {canAccessQuotations(user) && <Toggle
                                    label="Quotation expiry"
                                    description="Sent quotations expiring within two days, or already expired."
                                    {...toggle("notifications", "quotationExpiry")}
                                />}
                                <Toggle
                                    label="Notification sound"
                                    {...toggle("notifications", "sound")}
                                />

                                <div className="mt-6 max-w-sm">
                                    <Select
                                        label="Default reminder for new tasks — minutes before"
                                        options={["15", "30", "60", "120"]}
                                        {...bind("notifications", "reminderBefore")}
                                    />
                                </div>

                                <p className="mt-5 text-xs leading-6 text-slate-700">
                                    In-app reminders work while CRM is open. Sound requires interaction with the page. Email and WhatsApp delivery are separate features.
                                </p>
                            </Section>
                        )}

                        {tab === "workspace" && (
                            <Section
                                title="Workspace preferences"
                                description="Choose your workspace display preferences."
                            >
                                <div className="grid gap-4 sm:grid-cols-2">
                                    <Select
                                        label="Sidebar behaviour"
                                        options={["Hover to expand", "Always expanded"]}
                                        {...bind("workspace", "sidebar")}
                                    />
                                    <Select
                                        label="Default division"
                                        options={["All divisions", ...divisions]}
                                        {...bind("workspace", "defaultDivision")}
                                    />
                                    <Select
                                        label="Table rows per page"
                                        options={["10", "25", "50"]}
                                        {...bind("workspace", "rowsPerPage")}
                                    />
                                    <Select
                                        label="Date format"
                                        options={["DD MMM YYYY", "DD/MM/YYYY", "YYYY-MM-DD"]}
                                        {...bind("workspace", "dateFormat")}
                                    />
                                </div>

                                <div className="mt-7 rounded-xl border border-slate-200 p-5">
                                    <h3 className="text-sm font-bold text-slate-950">
                                        Data & workspace controls
                                    </h3>
                                    <p className="mt-2 text-xs leading-6 text-slate-700">
                                        Sidebar, default division, table page size and display date preferences apply to your account.
                                    </p>
                                </div>
                            </Section>
                        )}
                    </fieldset>

                    {saveError && <p role="alert" className="mx-4 mb-3 rounded-lg bg-rose-50 p-3 text-xs text-rose-900">{saveError}</p>}
                    <footer className="flex flex-wrap items-center justify-between gap-4 border-t border-slate-200 bg-slate-50 px-5 py-4 sm:px-7">
                        <p
                            role="status"
                            className="flex items-center gap-2 text-xs font-medium text-slate-700"
                        >
                            {notice ? (
                                <>
                                    {notice === "Settings saved to your workspace." && (
                                        <Check size={16} className="text-teal-800" />
                                    )}
                                    {notice}
                                </>
                            ) : (
                                ["company", "leads", "quotation"].includes(tab) && !settings.canManageShared ? "Only the Owner can save these business settings." : "Save to apply your changes across devices."
                            )}
                        </p>

                        <div className="flex flex-wrap gap-2"><Button variant="secondary" disabled={saving} onClick={reloadSaved}>Reload saved settings</Button><Button type="submit" disabled={saving || (["company", "leads", "quotation"].includes(tab) && !settings.canManageShared)}>
                            <Save size={16} />
                            {saving ? "Saving..." : "Save changes"}
                        </Button></div>
                    </footer>
                </form>
            </Card>
            {tab === "profile" && <PasswordChange />}
            {tab === "workspace" && user.isOwner && <OperationsPanel />}
            </>
            )}
            </div>
        </div>
    );
}
