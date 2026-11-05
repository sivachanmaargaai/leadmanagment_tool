export function datePreset(preset, at = new Date()) {
  const parts = new Intl.DateTimeFormat("en-CA", { timeZone: "Asia/Kolkata", year: "numeric", month: "2-digit", day: "2-digit" }).formatToParts(at);
  const values = Object.fromEntries(parts.map(({ type, value }) => [type, value]));
  const today = `${values.year}-${values.month}-${values.day}`;
  if (preset === "all") return { startDate: "", endDate: "" };
  if (preset === "today") return { startDate: today, endDate: today };
  if (preset === "month") return { startDate: `${values.year}-${values.month}-01`, endDate: today };
  if (preset === "week") {
    const day = new Date(`${today}T00:00:00Z`);
    day.setUTCDate(day.getUTCDate() - (day.getUTCDay() + 6) % 7);
    return { startDate: day.toISOString().slice(0, 10), endDate: today };
  }
  return null;
}

export function csvText(columns, rows) {
  const cell = (value) => {
    let text = String(value ?? "");
    const formulaStart = [...text].find((character) => character.charCodeAt(0) > 31 && !/\s/.test(character));
    if ((formulaStart && "=+@-".includes(formulaStart)) || /^[\t\r\n]/.test(text)) text = "'" + text;
    return `"${text.replaceAll('"', '""')}"`;
  };
  return "\uFEFF" + [columns.map((column) => cell(column.label)).join(","),
    ...rows.map((row) => columns.map((column) => cell(column.exportValue ? column.exportValue(row) : row[column.key])).join(","))].join("\r\n");
}

export function saveFile(blob, filename) {
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url; anchor.download = filename;
  document.body.appendChild(anchor); anchor.click(); anchor.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

export async function exportReportPdf(title, columns, rows, notes) {
  const [{ jsPDF }, { autoTable }] = await Promise.all([import("jspdf"), import("jspdf-autotable")]);
  const doc = new jsPDF({ orientation: "landscape" });
  doc.setFontSize(17); doc.setTextColor(7, 88, 84); doc.text(`ENGEN CRM - ${title}`, 14, 18);
  doc.setFontSize(9); doc.setTextColor(30);
  const lines = doc.splitTextToSize(notes, 265);
  doc.text(lines, 14, 27);
  autoTable(doc, { startY: 31 + lines.length * 4, head: [columns.map((column) => column.label)],
    body: rows.map((row) => columns.map((column) => String(column.exportValue ? column.exportValue(row) : row[column.key] ?? ""))),
    styles: { fontSize: 8, cellPadding: 3, overflow: "linebreak" }, headStyles: { fillColor: [7, 88, 84] }, margin: { bottom: 15 } });
  const pages = doc.getNumberOfPages();
  for (let page = 1; page <= pages; page++) {
    doc.setPage(page); doc.setFontSize(8); doc.text(`Page ${page} of ${pages}`, 280, 203, { align: "right" });
  }
  doc.save(`engen-${title.toLowerCase().replaceAll(" ", "-")}-report.pdf`);
}
