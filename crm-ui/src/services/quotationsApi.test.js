import assert from "node:assert/strict";
import test from "node:test";
import { apiRequest } from "./apiClient.js";
import { createQuotation, updateQuotation, uploadQuotationRevision, getQuotationPdf, quotationPayload, deleteQuotation } from "./quotationsApi.js";

test("quotation DTO excludes client totals, binary history, ids and item ids", () => {
  const payload = quotationPayload({ id: "client", version: 5, number: "NEM-1", amount: "", totals: { total: 1 }, versions: [{}],
    items: [{ id: "item", description: "IoT", quantity: "2", rate: "100", billing: "One-time" }] });
  assert.equal(payload.amount, 0);
  assert.deepEqual(payload.items, [{ description: "IoT", quantity: "2", rate: "100", billing: "One-time" }]);
  for (const field of ["id", "version", "totals", "versions"]) assert.equal(field in payload, false);
});

test("generated creation uses JSON; uploads use browser multipart headers", async (t) => {
  const calls = [];
  t.mock.method(globalThis, "fetch", async (url, options) => {
    calls.push({ url, ...options });
    return { ok: true, status: 201, json: async () => ({ id: "server" }) };
  });
  await createQuotation({ number: "NEM-1", items: [] });
  await createQuotation({ number: "EXT-1", items: [], amount: "250" }, new File(["%PDF-"], "external.pdf", { type: "application/pdf" }));
  assert.equal(calls[0].headers["Content-Type"], "application/json");
  assert.equal(calls[1].headers["Content-Type"], undefined);
  assert.ok(calls[1].body instanceof FormData);
  assert.equal(JSON.parse(calls[1].body.get("metadata")).amount, 250);
  assert.equal(calls[1].body.get("file").name, "external.pdf");
});

test("status, document revision, upload and archive include the expected version", async (t) => {
  const calls = [];
  t.mock.method(globalThis, "fetch", async (url, options) => {
    calls.push({ url, ...options });
    return options.method === "DELETE" ? { ok: true, status: 204 } : { ok: true, status: 200, json: async () => ({ id: "server" }) };
  });
  const quote = { id: "server", version: 3 };
  await updateQuotation(quote, { status: "Sent" });
  await updateQuotation(quote, { document: { number: "NEM-2", items: [] } });
  await uploadQuotationRevision(quote, new File(["%PDF-"], "revision.pdf"));
  await deleteQuotation(quote);
  assert.deepEqual(JSON.parse(calls[0].body), { status: "Sent", expectedVersion: 3 });
  assert.equal(JSON.parse(calls[1].body).expectedVersion, 3);
  assert.equal(calls[2].body.get("expectedVersion"), "3");
  assert.match(calls[3].url, /expectedVersion=3$/);
});

test("PDF fetch accepts only revision routes and surfaces server errors", async (t) => {
  const version = { pdfPath: "/api/quotations/abc-123/versions/def-456/pdf" };
  const pdf = new Blob(["%PDF-"], { type: "application/pdf" });
  const fetch = t.mock.method(globalThis, "fetch", async () => new Response(pdf));
  assert.equal((await getQuotationPdf(version)).type, "application/pdf");
  assert.throws(() => getQuotationPdf({ pdfPath: "https://elsewhere.example/file.pdf" }), /unavailable/);
  fetch.mock.mockImplementation(async () => new Response(JSON.stringify({ detail: "PDF revision not found" }), { status: 404 }));
  await assert.rejects(getQuotationPdf(version), /PDF revision not found/);
  fetch.mock.mockImplementation(async () => new Response("<html>proxy error</html>", { headers: { "Content-Type": "text/html" } }));
  await assert.rejects(apiRequest(version.pdfPath, { responseType: "blob" }), /did not return a PDF/);
});
