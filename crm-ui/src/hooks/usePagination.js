import { useState } from "react";
import { runtimeSettings } from "../lib/runtimeSettings";
export default function usePagination(rows) {
  const size = runtimeSettings().workspace.rowsPerPage;
  const key = `${size}:${rows.map((item) => item.id || item.name).join(",")}`;
  const [cursor, setCursor] = useState({ key, page: 1 });
  const pages = Math.max(1, Math.ceil(rows.length / size));
  const page = Math.min(cursor.key === key ? cursor.page : 1, pages);
  return { rows: rows.slice((page - 1) * size, page * size), page, pages, total: rows.length, setPage: (value) => setCursor({ key, page: value }) };
}
