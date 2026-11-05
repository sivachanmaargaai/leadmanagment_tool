import { Card, CardHeading, EmptyState } from "../ui";

export default function ReportBars({ title, items, valueKey = "count", onSelect }) {
  const maximum = Math.max(1, ...items.map((item) => item[valueKey]));
  return <Card><CardHeading title={title} description={onSelect ? "Select a bar to filter the report." : undefined} /><div className="space-y-3 px-4 pb-4">
    {!items.length && <EmptyState title="No data for this period" />}
    {items.map((item) => {
      const content = <><span className="flex justify-between gap-3 text-xs"><span className="break-words text-slate-800">{item.name}</span><strong className="text-slate-950">{item[valueKey]}</strong></span><span className="mt-1.5 block h-2 overflow-hidden rounded-full bg-slate-100"><span className="block h-full rounded-full bg-teal-700 transition-[width] duration-300 motion-reduce:transition-none" style={{ width: `${item[valueKey] / maximum * 100}%` }} /></span></>;
      return onSelect ? <button type="button" key={item.name} className="block min-h-10 w-full rounded-lg text-left outline-offset-4 hover:opacity-80 focus-visible:outline-2 focus-visible:outline-teal-600" onClick={() => onSelect(item.name)}>{content}</button> : <div key={item.name}>{content}</div>;
    })}
  </div></Card>;
}
