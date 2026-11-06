import { useEffect, useRef, useState } from "react";
import { Plus, CalendarDays } from "lucide-react";
import Sidebar from "./components/Sidebar";
import Header from "./components/Header";
import LeadRegister from "./components/LeadRegister";
import AddLeadModal from "./components/AddLeadModal";
import { Button, Card } from "./components/ui";
import Dashboard from "./pages/Dashboard";
import { divisions } from "./data/crm";
import {
  createLead,
  updateLead,
  deleteLead,
} from "./services/leadsApi";
import Settings from "./pages/Settings";
import Quotations from "./pages/Quotations";
import FollowUps from "./pages/FollowUps";
import useWorkspaceData from "./hooks/useWorkspaceData";
import PageTransition from "./components/PageTransition";
import { notificationAlerts } from "./lib/notificationAlerts";
import useNotificationSound from "./hooks/useNotificationSound";

import Customers from "./pages/Customers";
import Reports from "./pages/Reports";
import SettingsProvider from "./components/settings/SettingsProvider";
import { canAccessQuotations } from "./lib/permissions";
import { useSettings } from "./context/SettingsContext";
export default function App(props) {
  return <SettingsProvider user={props.user} onProfileUpdated={props.onProfileUpdated} onLogout={props.onLogout}><Workspace {...props} /></SettingsProvider>;
}

function Workspace({ user, onLogout, signingOut }) {
  const canQuotes = canAccessQuotations(user);
  const { settings: preferences } = useSettings();
  const [page, setPage] = useState("Dashboard");

  const [revision, setRevision] = useState(0);
  const [leadsError, setLeadsError] = useState("");
  const [leadSaving, setLeadSaving] = useState(false);
  const leadSaveLock = useRef(false);
  const changed = () => setRevision((value) => value + 1);

  const [leadSaveError, setLeadSaveError] = useState("");
  const [division, setDivision] = useState(preferences.workspace.defaultDivision);
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [formOpen, setFormOpen] = useState(false);
  useEffect(() => {
    const media = window.matchMedia("(min-width: 1024px)");
    const closeDrawer = () => setSidebarOpen(false);
    media.addEventListener("change", closeDrawer);
    return () => media.removeEventListener("change", closeDrawer);
  }, []);
  const overview = useWorkspaceData("overview", division, revision, "", preferences.notifications);
  const data = overview.data;
  const [now, setNow] = useState(Date.now);
  useEffect(() => { const timer = setInterval(() => setNow(Date.now()), 30000); return () => clearInterval(timer); }, []);
  const alerts = notificationAlerts({ leads: data?.alertLeads || [], followUps: data?.alertFollowUps || [], quotes: canQuotes ? data?.alertQuotes || [] : [], notifications: preferences.notifications, division, now });
  useNotificationSound(alerts, preferences.notifications.sound);
  useEffect(() => {
    const changed = (event) => setDivision(event.detail);
    window.addEventListener("crm:default-division-changed", changed);
    return () => window.removeEventListener("crm:default-division-changed", changed);
  }, []);

  const hasLeadContent = ["Dashboard", "Leads"].includes(page);

  async function saveLead(lead) {
    if (leadSaveLock.current) return;
    leadSaveLock.current = true;
    setLeadSaving(true);
    setLeadSaveError("");
    try {
      await createLead(lead);
      changed();
      setFormOpen(false);
      setLeadsError("");
    } catch (error) {
      setLeadSaveError(error.message || "Failed to save lead");
    } finally {
      leadSaveLock.current = false;
      setLeadSaving(false);
    }
  }

  function navigate(nextPage) {
    if (nextPage === "Quotations" && !canQuotes) return;
    setPage(nextPage);
    setSidebarOpen(false);
    window.scrollTo({ top: 0, behavior: "instant" });
  }



  async function handleUpdateLead(id, updates) {
    try {
      const updatedLead = await updateLead(id, updates);

      changed();

      setLeadsError("");
      return updatedLead;
    } catch (error) {
      setLeadsError(error.message);
      throw error;
    }
  }

  async function handleDeleteLead(id, version) {
    try {
      await deleteLead(id, version);

      changed();

      setLeadsError("");
      return true;
    } catch (error) {
      setLeadsError(error.message);
      throw error;
    }
  }

  return (
    <div className="min-h-screen bg-[#f4f7f5] font-sans text-slate-900 antialiased selection:bg-lime-200 selection:text-teal-950 [&_button]:cursor-pointer">
      <Sidebar
        page={page}
        canViewQuotations={canQuotes}
        alwaysExpanded={preferences.workspace.sidebar === "Always expanded"}
        onNavigate={navigate}
        leadCount={data?.metrics?.leads.total ?? "�"}
        open={sidebarOpen}
        onClose={() => setSidebarOpen(false)}
      />

      <main className={`min-w-0 ${preferences.workspace.sidebar === "Always expanded" ? "lg:ml-60" : "lg:ml-18"}`}>
        <Header
          key={page}
          page={page}
          alerts={alerts}
          alertError={overview.error}
          user={user}
          onLogout={onLogout}
          signingOut={signingOut}
          onMenu={() => setSidebarOpen(true)}
        />

        <PageTransition key={`content-${page}`} className="mx-auto min-w-0 max-w-400 px-3 py-4 sm:px-5 sm:py-5 xl:px-6">
          <section className="mb-4 flex items-start justify-between gap-3">
            <div className="min-w-0 flex-1">
              <p className="text-[10px] font-bold tracking-[0.18em] text-teal-800">
                ENGEN CRM
              </p>
              <h1 className="mt-1.5 text-xl font-bold tracking-tight text-slate-950 sm:text-2xl">
                {page === "Dashboard" ? "Workspace overview" : page}
              </h1>
              <p className="mt-1.5 max-w-md text-xs leading-5 text-slate-700">
                Your customers, conversations and opportunities. Connected.
              </p>
            </div>

            {hasLeadContent && (
              <Button onClick={() => setFormOpen(true)}>
                <Plus size={17} />
                Add lead
              </Button>
            )}
          </section>

          {hasLeadContent && (
            <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
              <label className="flex items-center gap-3 text-xs font-semibold text-slate-800">
                Division
                <select
                  value={division}
                  onChange={(event) => setDivision(event.target.value)}
                  className="rounded-lg border border-slate-300 bg-white px-3 py-2 text-xs font-medium text-slate-900 outline-none focus:border-teal-600 focus:ring-2 focus:ring-teal-100"
                >
                  <option>All divisions</option>
                  {divisions.map((name) => (
                    <option key={name}>{name}</option>
                  ))}
                </select>
              </label>

              <span className="flex items-center gap-2 text-xs font-medium text-slate-700">
                <CalendarDays size={15} />
                {new Intl.DateTimeFormat("en-IN", {
                  dateStyle: "medium",
                  timeZone: "Asia/Kolkata",
                }).format(new Date())}
              </span>
            </div>
          )}

          {overview.loading && !data && (
            <div className="mb-4 rounded-lg bg-blue-50 p-3 text-sm text-blue-800">
              Loading leads from backend...
            </div>
          )}

          {leadsError && (
            <div role="alert" className="mb-4 rounded-lg bg-red-50 p-3 text-sm text-red-800">
              Backend error: {leadsError}
            </div>
          )}

          {page === "Dashboard" ? (data ? (
            <Dashboard
              leads={data?.recentLeads || []}
              metrics={data?.metrics}
              onViewLeads={() => navigate("Leads")}
              followUps={data?.queue || []}
              now={now}
              onViewFollowUps={() => navigate("Follow-ups")}
            />
          ) : <Card className="p-5"><p role={overview.error ? "alert" : "status"} className="text-sm text-slate-800">{overview.error || "Loading workspace summary..."}</p></Card>) : page === "Leads" ? (
            <LeadRegister division={division} revision={revision} onUpdateLead={handleUpdateLead}
              onDeleteLead={user.role === "Admin" ? handleDeleteLead : undefined} />
          ) : page === "Customers" ? (
            <Customers onChanged={changed} />
          ) : page === "Settings" ? (
            <Settings user={user} />
          ) : page === "Quotations" ? (
            canQuotes ? <Quotations onChanged={changed} /> : <Card className="p-4">Quotation access is disabled.</Card>
          ) : page === "Follow-ups" ? (
            <FollowUps now={now} onChanged={changed} />
          ) : page === "Reports" ? (
            <Reports onNavigate={navigate} />
          ) : (
            <Card className="flex flex-col items-center gap-4 px-5 py-10 text-center">
              <span className="text-[10px] font-bold tracking-widest text-teal-800">
                NEXT MODULE
              </span>
              <h2 className="text-2xl font-bold text-slate-950">{page}</h2>
              <p className="text-sm text-slate-700">
                This screen will be built in the next step.
              </p>
              <Button
                variant="secondary"
                onClick={() => navigate("Dashboard")}
              >
                Back to dashboard
              </Button>
            </Card>
          )}

          <footer className="mt-5 flex flex-wrap justify-between gap-2 text-[11px] font-medium text-slate-600">
            <span>ENGEN · Scaling Heights</span>
            <span>{divisions.join(" / ")}</span>
          </footer>
        </PageTransition>
      </main>

      {formOpen && (
        <AddLeadModal
          saving={leadSaving}
          saveError={leadSaveError}
          onClose={() => {
            setFormOpen(false);
            setLeadSaveError("");
          }}
          onSave={saveLead}
        />
      )}
    </div>
  );
}
