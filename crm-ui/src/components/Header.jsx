import { useState } from "react";
import { Bell, LogOut, Menu, X } from "lucide-react";
import { divisionLabel, initials } from "../data/crm";
import { IconButton } from "./ui";

export default function Header({ page, alerts, onMenu, user, onLogout, signingOut, alertError }) {
    const [notificationsOpen, setNotificationsOpen] = useState(false);

    return (
        <header className="relative z-30 flex h-16 min-w-0 items-center justify-between gap-3 border-b border-slate-200 bg-white px-3 shadow-sm shadow-slate-900/3 sm:px-5 xl:px-6">
            <IconButton
                className="lg:hidden"
                aria-label="Open navigation"
                onClick={onMenu}
            >
                <Menu size={21} />
            </IconButton>

            <span className="min-w-0 truncate text-sm font-semibold text-slate-900 lg:hidden">{page}</span>
            <div className="hidden items-center gap-3 text-xs text-slate-600 lg:flex">
                ENGEN Workspace
                <span className="text-slate-400">/</span>
                <strong className="font-semibold text-slate-900">{page}</strong>
            </div>

            <div className="ml-auto flex shrink-0 items-center gap-2 sm:gap-4">
                <span className="hidden items-center gap-2 text-xs font-medium text-slate-700 lg:flex">
                    <i className="size-1.5 rounded-full bg-teal-600" />
                    Team workspace
                </span>

                <div className="relative">
                    <IconButton
                        aria-label="Notifications"
                        aria-expanded={notificationsOpen}
                        onClick={() => setNotificationsOpen((value) => !value)}
                    >
                        <Bell size={20} />
                        {alerts.length > 0 && (
                            <i className="absolute right-2 top-1.5 size-1.5 rounded-full bg-rose-500 ring-2 ring-white" />
                        )}
                    </IconButton>

                    {notificationsOpen && (
                        <section className="fixed right-3 top-15 z-30 w-[calc(100vw-1.5rem)] max-w-sm overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-xl sm:absolute sm:right-0 sm:top-12 sm:w-85">
                            <header className="flex items-center justify-between border-b border-slate-200 px-4 py-3">
                                <strong className="text-sm text-slate-950">
                                    Needs attention
                                </strong>
                                <IconButton
                                    aria-label="Close notifications"
                                    onClick={() => setNotificationsOpen(false)}
                                >
                                    <X size={17} />
                                </IconButton>
                            </header>

                            <div className="max-h-80 overflow-y-auto">
                                {alerts.length === 0 ? (
                                    <p className="p-5 text-sm text-slate-700">
                                        No pending alerts in this division.
                                    </p>
                                ) : (
                                    alerts.map((lead) => (
                                        <article
                                            key={lead.id}
                                            className="flex gap-3 border-b border-slate-100 p-4 transition-colors hover:bg-rose-50/50"
                                        >
                                            <span className="mt-1.5 size-1.5 shrink-0 rounded-full bg-rose-500" />
                                            <div>
                                                <strong className="text-xs text-slate-950">
                                                    {lead.customer}
                                                </strong>
                                                <p className="mt-1 text-xs leading-5 text-slate-700">
                                                    {lead.description}
                                                </p>
                                                <p className="mt-2 text-[11px] font-medium text-teal-800">
                                                    {divisionLabel(lead.division)} · {lead.alertLabel || "High priority"}
                                                </p>
                                            </div>
                                        </article>
                                    ))
                                )}
                            </div>

                            <footer className="bg-slate-50 px-4 py-3 text-[11px] text-slate-600">
                                {alertError || "Up to 20 alerts per category · Open the register for all records"}
                            </footer>
                        </section>
                    )}
                </div>

                <div className="flex items-center gap-2 border-l border-slate-200 pl-3 sm:pl-4">
                    <span className="flex size-9 items-center justify-center rounded-full bg-lime-100 text-xs font-bold text-teal-950">
                        {initials(user?.name || "User")}
                    </span>
                    <div className="hidden sm:block">
                        <strong className="block max-w-36 truncate text-xs text-slate-950">{user?.name || "User"}</strong>
                        <small className="mt-1 block text-[11px] text-slate-600">
                            {user?.role === "Admin" ? "Workspace admin" : "Staff"}
                        </small>
                    </div>
                    <IconButton aria-label="Sign out" title="Sign out" disabled={signingOut} onClick={() => onLogout?.()}><LogOut size={18} /></IconButton>
                </div>
            </div>
        </header>
    );
}
