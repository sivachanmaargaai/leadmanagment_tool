import { useEffect, useRef, useState } from "react";
import { LayoutDashboard, Users, Building2, CalendarClock, FileText, BarChart3, Settings, Layers3, ArrowUpRight, X } from "lucide-react";

const navigation = [
  { name: "Dashboard", icon: LayoutDashboard }, { name: "Leads", icon: Users },
  { name: "Customers", icon: Building2 }, { name: "Follow-ups", icon: CalendarClock },
  { name: "Quotations", icon: FileText }, { name: "Reports", icon: BarChart3 },
];

function NavItem({ name, icon: Icon, active, count, expanded, onClick }) {
  return <button type="button" onClick={onClick} aria-label={name} aria-current={active ? "page" : undefined} title={expanded ? undefined : name}
    className={`group/item relative flex h-11 w-full items-center gap-3 overflow-hidden rounded-xl px-4 text-left text-sm font-semibold transition-colors duration-200 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-teal-700 motion-reduce:transition-none ${active ? "bg-lime-100 text-teal-950" : "text-slate-700"} hover:bg-teal-900 hover:text-white`}>
    <Icon size={20} className="shrink-0" />
    <span aria-hidden={!expanded} className={`whitespace-nowrap transition-opacity duration-150 motion-reduce:transition-none ${expanded ? "opacity-100" : "pointer-events-none opacity-0"}`}>{name}</span>
    {count !== undefined && <span aria-hidden={!expanded} className={`ml-auto rounded-md bg-teal-900/10 px-2 py-0.5 text-[11px] font-bold text-teal-950 group-hover/item:bg-white/15 group-hover/item:text-white ${expanded ? "opacity-100" : "opacity-0"}`}>{count}</span>}
  </button>;
}

export default function Sidebar({ page, onNavigate, leadCount, open, onClose, alwaysExpanded = false, canViewQuotations = false }) {
  const ref = useRef(null);
  const [desktop, setDesktop] = useState(() => window.matchMedia("(min-width: 1024px)").matches);
  const [hovered, setHovered] = useState(false);
  const [keyboardFocus, setKeyboardFocus] = useState(false);
  const [touchExpanded, setTouchExpanded] = useState(false);
  const expanded = !desktop || alwaysExpanded || hovered || keyboardFocus || touchExpanded;

  useEffect(() => {
    const media = window.matchMedia("(min-width: 1024px)");
    const resize = () => { setDesktop(media.matches); setHovered(false); setKeyboardFocus(false); setTouchExpanded(false); };
    media.addEventListener("change", resize);
    return () => media.removeEventListener("change", resize);
  }, []);

  useEffect(() => {
    if (desktop || !open) return;
    const previousFocus = document.activeElement;
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    ref.current.querySelector("button:not([tabindex='-1'])")?.focus();
    return () => {
      document.body.style.overflow = previousOverflow;
      if (previousFocus?.isConnected) previousFocus.focus();
    };
  }, [open, desktop]);

  function keyDown(event) {
    if (event.key === "Escape") {
      setHovered(false); setKeyboardFocus(false); setTouchExpanded(false);
      if (!desktop) onClose();
    }
    if (!desktop && open && event.key === "Tab") {
      const controls = [...ref.current.querySelectorAll("button:not([disabled]):not([tabindex='-1']), a[href], input, select")].filter((node) => node.getClientRects().length);
      const first = controls[0]; const last = controls.at(-1);
      if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last?.focus(); }
      if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first?.focus(); }
    }
  }

  function navigate(name) { setHovered(false); setTouchExpanded(false); onNavigate(name); }

  return <>
    {open && !desktop && <button type="button" aria-label="Close navigation overlay" onClick={onClose} className="fixed inset-0 z-40 bg-slate-950/35 backdrop-blur-sm lg:hidden" />}
    <aside ref={ref} aria-label="Workspace navigation" role={!desktop && open ? "dialog" : undefined} aria-modal={!desktop && open ? true : undefined} inert={!desktop && !open}
      data-expanded={expanded} data-desktop={desktop}
      onPointerEnter={(event) => { if (desktop && event.pointerType === "mouse") setHovered(true); }}
      onPointerLeave={(event) => { if (event.pointerType === "mouse") { setHovered(false); setKeyboardFocus(false); setTouchExpanded(false); } }}
      onPointerDown={() => setKeyboardFocus(false)}
      onFocusCapture={(event) => { if (desktop && event.target.matches(":focus-visible")) setKeyboardFocus(true); }}
      onBlurCapture={(event) => { if (!event.currentTarget.contains(event.relatedTarget)) setKeyboardFocus(false); }}
      onKeyDown={keyDown}
      className={`fixed inset-y-0 left-0 z-50 flex max-w-[calc(100vw-2rem)] flex-col overflow-x-hidden overflow-y-auto border-r border-slate-200 bg-white px-2.5 py-3 transition-[width,translate,box-shadow] duration-200 ease-out motion-reduce:transition-none lg:translate-x-0 ${expanded ? "w-64 lg:w-60 shadow-xl shadow-slate-950/10" : "w-64 lg:w-18 shadow-sm"} ${open ? "translate-x-0" : "-translate-x-full"}`}>
      <div className="relative mb-3 flex h-16 shrink-0 items-center border-b border-slate-200">
        <button type="button" aria-label="Toggle navigation width" aria-expanded={expanded} onClick={() => setTouchExpanded((value) => !value)} className={`absolute left-1 flex size-11 items-center justify-center rounded-xl bg-teal-900 text-lime-200 transition-opacity duration-150 ${expanded ? "pointer-events-none opacity-0" : "opacity-100"}`} tabIndex={expanded ? -1 : 0}><ArrowUpRight size={27} /></button>
        <img src={`${import.meta.env.BASE_URL}Engen%20logo%20Final.png`} alt="ENGEN — Scaling Heights" className={`pointer-events-none ml-3 h-13 w-36 max-w-none object-contain transition-opacity duration-150 ${expanded ? "opacity-100" : "opacity-0"}`} />
        {desktop && touchExpanded && !alwaysExpanded && <button type="button" aria-label="Collapse navigation" onClick={() => { setTouchExpanded(false); setHovered(false); setKeyboardFocus(false); }} className="absolute right-0 flex size-10 items-center justify-center rounded-lg text-slate-700 hover:bg-teal-50 focus-visible:outline-2 focus-visible:outline-teal-700"><X size={20} /></button>}
        {!desktop && <button type="button" aria-label="Close navigation" onClick={onClose} className="ml-auto rounded-lg p-2 text-slate-700 hover:bg-teal-50"><X size={20} /></button>}
      </div>
      <div className="mb-4 flex h-11 shrink-0 items-center gap-3 overflow-hidden rounded-xl bg-teal-50 px-4 text-teal-900">
        <Layers3 size={20} className="shrink-0" /><div aria-hidden={!expanded} className={`whitespace-nowrap transition-opacity duration-150 ${expanded ? "opacity-100" : "opacity-0"}`}><strong className="block text-xs">ENGEN Workspace</strong><small className="mt-0.5 block text-[10px] text-slate-700">All divisions. One workspace.</small></div>
      </div>
      <nav className="space-y-1" aria-label="Main navigation">{navigation.filter(({ name }) => name !== "Quotations" || canViewQuotations).map(({ name, icon }) => <NavItem key={name} name={name} icon={icon} active={page === name} expanded={expanded} count={name === "Leads" ? leadCount : undefined} onClick={() => navigate(name)} />)}</nav>
      <div className="mt-auto pt-5"><NavItem name="Settings" icon={Settings} active={page === "Settings"} expanded={expanded} onClick={() => navigate("Settings")} />
        <div aria-hidden={!expanded} className={`mt-3 whitespace-nowrap border-t border-slate-200 px-4 pt-3 transition-opacity duration-150 ${expanded ? "opacity-100" : "opacity-0"}`}><strong className="text-xs text-teal-950">Scaling Heights</strong><p className="mt-1 text-[10px] text-slate-700">ENGEN CRM · Team workspace</p></div>
      </div>
    </aside>
  </>;
}
