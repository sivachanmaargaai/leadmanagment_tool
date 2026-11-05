import { useState } from "react";
import {
    Users,
    Clock3,
    CheckCheck,
    Flag,
    ArrowUpRight,
    CalendarClock,
} from "lucide-react";
import { statuses } from "../data/crm";
import { formatFollowUpDate, isOverdue, matchesFollowUpTab } from "../lib/followUps";
import LeadTable from "../components/LeadTable";
import {
    Card,
    CardHeading,
    Avatar,
    EmptyState,
} from "../components/ui";

const progressColors = {
    New: "[&::-webkit-progress-value]:bg-teal-600 [&::-moz-progress-bar]:bg-teal-600",
    "In Progress":
        "[&::-webkit-progress-value]:bg-lime-600 [&::-moz-progress-bar]:bg-lime-600",
    "Follow-up":
        "[&::-webkit-progress-value]:bg-sky-600 [&::-moz-progress-bar]:bg-sky-600",
    Won: "[&::-webkit-progress-value]:bg-emerald-700 [&::-moz-progress-bar]:bg-emerald-700",
    Lost: "[&::-webkit-progress-value]:bg-rose-500 [&::-moz-progress-bar]:bg-rose-500",
};

function StatCard({ label, value, caption, icon: Icon, tone }) {
    return (
        <Card className="p-4 motion-safe:hover:-translate-y-0.5 motion-safe:transition-[box-shadow,transform] motion-safe:duration-200">
            <div className="flex items-center justify-between gap-3">
                <span className="text-xs font-medium text-slate-700">{label}</span>
                <span
                    className={`flex size-9 shrink-0 items-center justify-center rounded-xl ${tone}`}
                >
                    <Icon size={18} />
                </span>
            </div>

            <strong className="mt-2 block text-2xl font-bold tracking-tight text-slate-950">
                {value}
            </strong>
            <p className="mt-2 text-[11px] leading-5 text-slate-600">{caption}</p>
        </Card>
    );
}

function Pipeline({ leads, metrics }) {
    return (
        <Card>
            <CardHeading
                title="Lead pipeline"
                description="A clear picture of your opportunities."
            >
                <span className="rounded-md bg-lime-50 px-2.5 py-1.5 text-[11px] font-semibold text-teal-900">
                    {metrics?.total ?? leads.length} leads
                </span>
            </CardHeading>

            <div className="space-y-3.5 px-4 pb-4 pt-1">
                {statuses.map((status) => {
                    const count = metrics?.pipeline?.[status] ?? leads.filter(
                        (lead) => lead.status === status
                    ).length;

                    return (
                        <div
                            key={status}
                            className="grid grid-cols-[72px_1fr_16px] items-center gap-4"
                        >
                            <span className="text-xs font-medium text-slate-700">
                                {status}
                            </span>

                            <progress
                                aria-label={`${status}: ${count} leads`}
                                value={count}
                                max={(metrics?.total ?? leads.length) || 1}
                                className={`h-2 w-full appearance-none overflow-hidden rounded-full border-0 bg-slate-100 [&::-webkit-progress-bar]:rounded-full [&::-webkit-progress-bar]:bg-slate-100 [&::-webkit-progress-value]:rounded-full [&::-moz-progress-bar]:rounded-full ${progressColors[status]}`}
                            />

                            <strong className="text-right text-xs text-slate-900">
                                {count}
                            </strong>
                        </div>
                    );
                })}
            </div>

            <footer className="border-t border-slate-100 px-5 py-3 text-[11px] text-slate-600">
                Every conversation is a step forward.
            </footer>
        </Card>
    );
}

function FollowUpQueue({ followUps, now, onView, metrics }) {
    const pending = followUps.filter((item) => item.status === "Pending")
        .sort((a, b) => Date.parse(a.dueAt) - Date.parse(b.dueAt));
    const today = metrics?.Today ?? pending.filter((item) => matchesFollowUpTab(item, "Today", now)).length;
    const overdue = metrics?.Overdue ?? pending.filter((item) => isOverdue(item, now)).length;

    return (
        <Card className="flex flex-col">
            <CardHeading
                title="Follow-up queue"
                description="Keep the conversation moving."
            >
                <span className="flex size-9 items-center justify-center rounded-xl bg-teal-50 text-teal-800">
                    <CalendarClock size={18} />
                </span>
            </CardHeading>

            <div className="px-4">
                <div className="mb-3 grid grid-cols-2 gap-3">
                    <button type="button" onClick={onView} className="rounded-xl bg-teal-50 p-3 text-left text-xs font-semibold text-teal-950 hover:bg-teal-100">Today <strong className="mt-1 block text-xl">{today}</strong></button>
                    <button type="button" onClick={onView} className="rounded-xl bg-rose-50 p-3 text-left text-xs font-semibold text-rose-900 hover:bg-rose-100">Overdue <strong className="mt-1 block text-xl">{overdue}</strong></button>
                </div>
                {pending.length === 0 ? (
                    <EmptyState
                        icon={CheckCheck}
                        title="You're all caught up"
                        description="No scheduled follow-ups are pending."
                    />
                ) : (
                    pending.slice(0, 3).map((lead) => (
                        <div
                            key={lead.id}
                            className="flex gap-3 border-b border-slate-100 py-3 last:border-0"
                        >
                            <Avatar name={lead.customer} />
                            <div>
                                <strong className="text-xs font-semibold text-slate-950">
                                    {lead.customer}
                                </strong>
                                <p className="mt-1 text-xs leading-5 text-slate-700">
                                    {lead.purpose}
                                </p>
                                <small className="mt-2 block text-[11px] text-teal-800">
                                    {formatFollowUpDate(lead.dueAt)} IST · {lead.assignedTo}
                                </small>
                            </div>
                        </div>
                    ))
                )}
            </div>

            <div className="mx-4 mb-4 mt-auto pt-3">
                <button type="button" onClick={onView} className="flex w-full items-center gap-2 rounded-lg bg-lime-50 px-3 py-3 text-left text-xs font-semibold text-teal-900 hover:bg-lime-100">
                    <Clock3 size={15} />
                    {metrics ? metrics.All - metrics.Completed : pending.length} pending · View follow-ups
                </button>
            </div>
        </Card>
    );
}

export default function Dashboard({ metrics, leads, onViewLeads, followUps = [], now, onViewFollowUps }) {
    const [initialNow] = useState(Date.now);
    const active = leads.filter(
        (lead) => !["Won", "Lost"].includes(lead.status)
    );
    const won = leads.filter((lead) => lead.status === "Won");
    const high = active.filter((lead) => lead.priority === "High");

    return (
        <div className="space-y-4">
            <section className="relative flex items-center justify-between gap-5 overflow-hidden rounded-2xl bg-teal-950 px-5 py-5 shadow-md shadow-teal-950/10 sm:px-6">
                <div className="relative z-10">
                    <p className="text-[10px] font-semibold tracking-[0.2em] text-lime-200">
                        SCALING HEIGHTS, TOGETHER
                    </p>
                    <h2 className="mt-2 text-xl font-semibold leading-tight tracking-tight text-white sm:text-2xl">
                        Good relationships.
                        <br />
                        Great possibilities.
                    </h2>
                    <p className="mt-2 max-w-md text-xs leading-5 text-teal-100">
                        {metrics?.leads.active ?? active.length} active leads. {metrics?.leads.high ?? high.length} high-priority
                        opportunities. Your next step starts here.
                    </p>
                    <button
                        type="button"
                        onClick={onViewLeads}
                        className="mt-3 inline-flex items-center gap-2 rounded-md text-xs font-semibold text-lime-200 transition-colors hover:text-white focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-lime-200"
                    >
                        Explore your leads <ArrowUpRight size={16} />
                    </button>
                </div>

                <div
                    aria-hidden="true"
                    className="relative mr-8 hidden shrink-0 lg:block"
                >
                    <div className="flex size-32 items-center justify-center rounded-full border border-lime-200/30 text-lime-200 ring-18 ring-white/3">
                        <ArrowUpRight size={70} strokeWidth={1.2} />
                    </div>
                    <i className="absolute -top-3 left-4 size-3 rounded-full bg-lime-200" />
                    <i className="absolute -right-5 top-14 size-2.5 rounded-full bg-teal-300" />
                    <i className="absolute -left-4 bottom-0 size-4 rounded-full bg-rose-300" />
                </div>

                <div
                    aria-hidden="true"
                    className="pointer-events-none absolute -bottom-52 -right-20 size-110 rounded-full border border-white/10 ring-40 ring-white/3"
                />
            </section>

            <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
                <StatCard
                    label="Total leads"
                    value={metrics?.leads.total ?? leads.length}
                    caption="Across selected divisions"
                    icon={Users}
                    tone="bg-teal-50 text-teal-800"
                />
                <StatCard
                    label="Active leads"
                    value={metrics?.leads.active ?? active.length}
                    caption="Opportunities in progress"
                    icon={Clock3}
                    tone="bg-lime-100 text-lime-900"
                />
                <StatCard
                    label="Won leads"
                    value={metrics?.leads.won ?? won.length}
                    caption="Successfully converted"
                    icon={CheckCheck}
                    tone="bg-emerald-50 text-emerald-800"
                />
                <StatCard
                    label="High priority"
                    value={metrics?.leads.high ?? high.length}
                    caption="Ready for your attention"
                    icon={Flag}
                    tone="bg-rose-50 text-rose-800"
                />
            </div>

            <div className="grid gap-4 md:grid-cols-[1.1fr_1fr]">
                <Pipeline leads={leads} metrics={metrics?.leads} />
                <FollowUpQueue metrics={metrics?.followUps} followUps={followUps} now={now ?? initialNow} onView={onViewFollowUps} />
            </div>

            <LeadTable leads={leads} compact onViewAll={onViewLeads} />
        </div>
    );
}
