import { initials } from "../data/crm";

export function Button({
    children,
    variant = "primary",
    className = "",
    type = "button",
    ...props
}) {
    const variants = {
        primary:
            "border-teal-800 bg-teal-800 text-white hover:border-teal-950 hover:bg-teal-950",
        secondary:
            "border-slate-300 bg-white text-slate-800 hover:border-teal-300 hover:bg-teal-50",
    };

    return (
        <button
            type={type}
            className={`inline-flex min-h-10 shrink-0 items-center justify-center gap-2 rounded-lg border px-3.5 py-2 text-xs font-semibold transition-[background-color,border-color,box-shadow,transform] duration-200 active:scale-[0.98] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-teal-700 disabled:cursor-not-allowed disabled:opacity-50 motion-reduce:transform-none motion-reduce:transition-none ${variants[variant]} ${className}`}
            {...props}
        >
            {children}
        </button>
    );
}

export function IconButton({ children, className = "", ...props }) {
    return (
        <button
            type="button"
            className={`relative inline-flex size-10 shrink-0 items-center justify-center rounded-lg text-slate-700 transition-colors duration-150 hover:bg-teal-50 hover:text-teal-900 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-teal-700 disabled:cursor-not-allowed disabled:opacity-50 motion-reduce:transition-none ${className}`}
            {...props}
        >
            {children}
        </button>
    );
}

export function Card({ children, className = "" }) {
    return (
        <section
            className={`min-w-0 rounded-2xl border border-slate-200 bg-white shadow-sm shadow-slate-900/8 transition-shadow duration-200 hover:shadow-md hover:shadow-slate-900/8 motion-reduce:transition-none ${className}`}
        >
            {children}
        </section>
    );
}

export function CardHeading({ title, description, children }) {
    return (
        <div className="flex min-w-0 flex-wrap items-center justify-between gap-3 px-4 py-4">
            <div>
                <h2 className="text-sm font-bold text-slate-950">{title}</h2>
                {description && (
                    <p className="mt-1 text-xs leading-relaxed text-slate-600">
                        {description}
                    </p>
                )}
            </div>
            {children}
        </div>
    );
}

export function Avatar({ name }) {
    return (
        <span className="flex size-9 shrink-0 items-center justify-center rounded-xl bg-teal-50 text-xs font-bold text-teal-900">
            {initials(name)}
        </span>
    );
}

export function EmptyState({ icon: Icon, title, description }) {
    return (
        <div className="flex flex-col items-center gap-2 px-4 py-7 text-center">
            {Icon && <Icon size={27} className="text-teal-700" />}
            <strong className="text-sm font-semibold text-slate-800">
                {title}
            </strong>
            {description && (
                <p className="text-xs leading-relaxed text-slate-600">
                    {description}
                </p>
            )}
        </div>
    );
}
