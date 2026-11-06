r"""Seed five clearly labelled records per module and exercise the live local API.

Run from backend: .\venv\Scripts\python.exe -B scripts/seed_and_verify.py
Existing non-QA records are never updated or deleted. Re-runs reuse QA records.
Temporary DELETE checks retain archived follow-up/PDF history by design.
"""
import hashlib
import json
import re
import sys
from datetime import datetime, timedelta, timezone
from io import BytesIO
from pathlib import Path
from uuid import uuid4

import httpx
from pypdf import PdfReader
from api_auth import authenticate_client, end_test_session

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from app.schemas.quotation import QuotationDocument, totals
from app.services.quotation_pdf import generate_pdf

API = "http://127.0.0.1:8000"
IST = timezone(timedelta(hours=5, minutes=30))
LABEL = "[QA TEST] "
PREFIX = "QA-DEMO-"
COMPANIES = ["Aster Embedded Systems", "Beacon IoT Labs", "Cedar Cloud Solutions", "Delta Automation", "Elm Controls"]
DIVISIONS = ["nemilink", "MMC", "ClearCode Labs", "nemilink", "MMC"]
STATUSES = ["New", "In Progress", "Follow-up", "Won", "Lost"]
PRIORITIES = ["High", "Medium", "High", "Low", "Medium"]
SOURCES = ["Direct Enquiry", "Referral", "Known Network", "Website", "Phone"]
STAFF = ["Admin", "Priya", "Arun", "Admin", "Priya"]
PRODUCTS = ["Industrial IoT gateway", "Embedded sensor controller", "Cloud monitoring dashboard", "Edge AI prototype", "Firmware integration service"]


class Verification:
    def __init__(self):
        self.client = httpx.Client(base_url=API, timeout=40)
        self.checks = []
        self.routes = []
        self.covered = set()
        self.seeded = {}
        self.run = "QA-CHECK-" + uuid4().hex[:10].upper()

    def assert_true(self, condition, name):
        self.checks.append({"check": name, "passed": bool(condition)})
        if not condition:
            raise AssertionError(name)

    def request(self, method, path, expected=200, label=None, **kwargs):
        result = self.client.request(method, path, **kwargs)
        template = path.split("?")[0]
        for candidate_method, candidate_path in self.routes:
            pattern = "^" + re.sub(r"\{[^}]+\}", "[^/]+", candidate_path) + "$"
            if candidate_method == method and re.match(pattern, template):
                template = candidate_path
                break
        passed = result.status_code == expected
        check = {"check": label or f"{method} {template}", "method": method, "endpoint": template,
                 "expectedStatus": expected, "actualStatus": result.status_code, "passed": passed}
        if not passed:
            check["error"] = result.text[:1000]
        self.checks.append(check)
        if not passed:
            raise AssertionError(f"{method} {path}: expected {expected}, got {result.status_code}: {result.text[:500]}")
        if 200 <= expected < 300:
            self.covered.add((method, template))
        if expected == 204:
            return None
        return result if result.headers.get("content-type", "").startswith("application/pdf") else result.json()

    def ref(self, i):
        return {"name": "[QA TEST] Reference " + str(i + 1), "company": "QA Partner Network",
                "email": f"reference{i + 1}@example.test", "phone": ""} if SOURCES[i] in ["Referral", "Known Network"] else None

    def customer_data(self, i, name=None):
        return {"name": name or LABEL + COMPANIES[i], "divisions": [DIVISIONS[i]], "type": "Company",
                "contacts": [{"name": f"QA Contact {i + 1}", "designation": "Project coordinator",
                              "email": f"qa.customer{i + 1}@example.test", "phone": ""},
                             {"name": f"QA Technical Contact {i + 1}", "email": f"qa.tech{i + 1}@example.test"}],
                "city": ["Chennai", "Coimbatore", "Bengaluru", "Chennai", "Hosur"][i], "state": "Tamil Nadu" if i != 2 else "Karnataka",
                "assignedTo": STAFF[i], "leadSource": SOURCES[i], "referredBy": self.ref(i),
                "referenceNotes": "Synthetic referral for QA only" if self.ref(i) else "",
                "notes": "TEST DATA ONLY. Added for CRM API and UI verification."}

    def lead_data(self, i, name=None):
        return {"customer": name or LABEL + COMPANIES[i], "contact": f"QA Contact {i + 1}", "division": DIVISIONS[i],
                "description": f"TEST DATA ONLY: {PRODUCTS[i]} evaluation and quotation request.",
                "status": STATUSES[i], "priority": PRIORITIES[i], "leadSource": SOURCES[i],
                "referredBy": self.ref(i), "referenceNotes": "Synthetic network lead for testing" if self.ref(i) else ""}

    def quote_data(self, i, number=None):
        today = datetime.now(IST).date()
        billing = ["One-time", "Monthly", "Yearly", "One-time", "One-time"][i]
        return {"number": number or PREFIX + str(i + 1).zfill(3), "customer": LABEL + COMPANIES[i],
                "contact": f"QA Contact {i + 1}", "division": DIVISIONS[i], "currency": "INR",
                "date": str(today if i < 4 else today - timedelta(days=20)),
                "validUntil": str(today + timedelta(days=15) if i < 4 else today - timedelta(days=1)),
                "status": "Draft", "tax": "18" if i < 4 else "0", "amount": "7500.00" if i == 4 else "0",
                "billing": billing, "items": [] if i == 4 else [
                    {"description": "QA SAMPLE: " + PRODUCTS[i], "quantity": "2" if i == 0 else "1",
                     "rate": ["12500.00", "2500.00", "15000.00", "35000.00"][i], "billing": billing}],
                "terms": "TEST QUOTATION ONLY - not a commercial offer.\nPayment, delivery and warranty terms are sample text."}

    def fixture_pdf(self, document):
        data = dict(document)
        if not data["items"]:
            data["items"] = [{"description": "QA SAMPLE: Imported firmware service quotation",
                              "quantity": "1", "rate": data["amount"], "billing": data["billing"]}]
        model = QuotationDocument.model_validate(data)
        snapshot = model.model_dump(mode="json", by_alias=True)
        snapshot["totals"] = totals(model)
        return generate_pdf(snapshot)

    def collection(self, path):
        records = []
        page = 1
        while True:
            separator = "&" if "?" in path else "?"
            data = self.request("GET", f"{path}{separator}paged=true&pageSize=100&page={page}")
            records.extend(data["items"])
            if not data["hasMore"]:
                return records
            page += 1
            if page > 10000:
                raise AssertionError("Collection too large for demo verification")

    def verify_pdf(self, quote):
        latest = self.request("GET", f"/api/quotations/{quote['id']}/pdf")
        self.assert_true(latest.content.startswith(b"%PDF-"), "Latest PDF has valid signature")
        self.assert_true(len(PdfReader(BytesIO(latest.content)).pages) > 0, "Latest PDF is readable")
        for version in quote["versions"]:
            result = self.request("GET", version["pdfPath"])
            self.assert_true(hashlib.sha256(result.content).hexdigest() == version["sha256"],
                             f"{quote['number']} revision {version['revision']} hash retained")
        downloaded = self.request("GET", f"/api/quotations/{quote['id']}/pdf?download=true")
        self.assert_true("attachment" in downloaded.headers["content-disposition"], "PDF download attachment header")
        return latest.content

    def execute(self):
        schema = self.client.get("/openapi.json").raise_for_status().json()
        self.routes = sorted([(method.upper(), path) for path, item in schema["paths"].items()
                              if path.startswith("/api/") and not path.startswith(("/api/auth/", "/api/users", "/api/settings")) for method in item if method in {"get", "post", "put", "delete"}],
                             key=lambda item: ("{" in item[1], -len(item[1])))
        authenticate_client(self.client)
        self.request("GET", "/api/health")
        self.request("GET", "/api/db-health")
        customers = self.collection("/api/customers")
        leads = self.collection("/api/leads")
        followups = self.collection("/api/follow-ups")
        quotes = self.collection("/api/quotations")
        self.before = {"customers": len(customers), "leads": len(leads), "followUps": len(followups), "quotations": len(quotes)}
        self.original_ids = {"customers": {x["id"] for x in customers if not x["name"].startswith(LABEL)},
                             "leads": {x["id"] for x in leads if not x["customer"].startswith(LABEL)},
                             "followUps": {x["id"] for x in followups if not x["purpose"].startswith(PREFIX)},
                             "quotations": {x["id"] for x in quotes if not x["number"].startswith(PREFIX)}}
        saved_leads = []
        for i in range(5):
            customer = next((x for x in customers if x["name"] == LABEL + COMPANIES[i]), None)
            if customer is None:
                customer = self.request("POST", "/api/customers", 201, json=self.customer_data(i))
            customer = self.request("PUT", f"/api/customers/{customer['id']}", json={"expectedVersion": customer["version"], "notes": "TEST DATA ONLY. Customer API update verified.", "assignedTo": STAFF[i]})
            self.request("GET", f"/api/customers/{customer['id']}")
            self.seeded.setdefault("customers", []).append(customer["id"])
            lead = next((x for x in leads if x["customer"] == LABEL + COMPANIES[i]), None)
            if lead is None:
                lead = self.request("POST", "/api/leads", 201, json=self.lead_data(i))
            lead = self.request("PUT", f"/api/leads/{lead['id']}", json={"expectedVersion": lead["version"], "status": STATUSES[i], "priority": PRIORITIES[i]})
            self.request("GET", f"/api/leads/{lead['id']}")
            self.seeded.setdefault("leads", []).append(lead["id"])
            saved_leads.append(lead)
        print("SEEDED customers=5 leads=5", flush=True)

        at = datetime.now(timezone.utc)
        offsets = [timedelta(days=-1), timedelta(minutes=30), timedelta(days=2), timedelta(days=-2), timedelta(days=-3)]
        for i, lead in enumerate(saved_leads):
            purpose = PREFIX + f"FOLLOWUP-{i + 1}: " + ["Discuss hardware requirements", "Review embedded prototype", "Cloud software demo", "Confirm pilot scope", "Collect enquiry feedback"][i]
            task = next((x for x in followups if x["purpose"] == purpose), None)
            if task is None:
                task = self.request("POST", "/api/follow-ups", 201, json={"leadId": lead["id"], "purpose": purpose,
                    "dueAt": (at + offsets[i]).isoformat(), "type": ["Call", "Email", "Meeting", "Call", "Other"][i],
                    "assignedTo": STAFF[i], "priority": PRIORITIES[i], "reminderMinutes": 30,
                    "notes": "TEST DATA ONLY. Sample CRM follow-up."})
            if task["status"] != "Completed":
                update = {"expectedVersion": task["version"], "notes": "TEST DATA ONLY. Follow-up update verified."}
                if i >= 3:
                    update = {"expectedVersion": task["version"], "status": "Completed", "outcome": "Connected" if i == 3 else "Not interested",
                              "completionNotes": "QA test conversation completed. No real customer was contacted."}
                task = self.request("PUT", f"/api/follow-ups/{task['id']}", json=update)["record"]
            self.request("GET", f"/api/follow-ups/{task['id']}")
            self.seeded.setdefault("followUps", []).append(task["id"])
        upcoming = self.request("GET", "/api/follow-ups/upcoming")
        overdue = self.request("GET", "/api/follow-ups/overdue")
        self.assert_true(all(x["status"] == "Pending" for x in upcoming + overdue), "Due lists exclude completed follow-ups")
        self.assert_true(any(x["id"] in self.seeded["followUps"] for x in upcoming), "Seeded upcoming task is returned")
        self.assert_true(any(x["id"] in self.seeded["followUps"] for x in overdue), "Seeded overdue task is returned")
        print("SEEDED followUps=5 (3 pending, 2 completed)", flush=True)

        for i in range(5):
            document = self.quote_data(i)
            quote = next((x for x in quotes if x["number"] == document["number"]), None)
            if quote is None:
                if i == 4:
                    quote = self.request("POST", "/api/quotations/upload", 201, data={"metadata": json.dumps(document)},
                                         files={"file": (document["number"] + ".pdf", self.fixture_pdf(document), "application/pdf")})
                else:
                    quote = self.request("POST", "/api/quotations", 201, json=document)
            original = self.verify_pdf(quote)
            if i == 0 and len(quote["versions"]) == 1:
                document["terms"] += "\nRevision 2: QA document editing has been verified."
                quote = self.request("PUT", f"/api/quotations/{quote['id']}", json={"expectedVersion": quote["version"], "document": document})
                old = self.request("GET", quote["versions"][0]["pdfPath"])
                self.assert_true(old.content == original, "Generated edit retains exact previous PDF bytes")
            if i == 4 and len(quote["versions"]) == 1:
                document["amount"] = "8000.00"
                quote = self.request("POST", f"/api/quotations/{quote['id']}/revisions", 201,
                    data={"expectedVersion": str(quote["version"]), "metadata": json.dumps(document)},
                    files={"file": (document["number"] + "-R2.pdf", self.fixture_pdf(document), "application/pdf")})
                self.assert_true(quote["totals"]["One-time"]["total"] == 8000, "Imported revised amount persisted")
            quote = self.request("PUT", f"/api/quotations/{quote['id']}", json={"expectedVersion": quote["version"], "status": ["Draft", "Sent", "Accepted", "Rejected", "Expired"][i]})
            self.request("GET", f"/api/quotations/{quote['id']}")
            self.verify_pdf(quote)
            self.seeded.setdefault("quotations", []).append(quote["id"])
        print("SEEDED quotations=5 (4 generated, 1 imported; retained revisions)", flush=True)
        self.temporary_crud_checks(saved_leads[0])
        self.negative_checks(saved_leads[0])
        self.verify_report_endpoints()
        self.verify_final()

    def verify_report_endpoints(self):
        summary = self.request("GET", "/api/reports/summary?includeTestData=true")
        leads = self.request("GET", "/api/reports/leads?includeTestData=true")
        sales = self.request("GET", "/api/reports/sales?includeTestData=true")
        followups = self.request("GET", "/api/reports/follow-ups?includeTestData=true")
        self.assert_true(summary["totals"]["totalLeads"] == len(leads["rows"]), "Reports summary matches lead rows")
        self.assert_true(summary["totals"]["totalQuotations"] == len(sales["rows"]), "Reports summary matches quotation rows")
        self.assert_true(followups["summary"]["total"] == len(followups["rows"]), "Follow-up report count matches rows")

    def temporary_crud_checks(self, linked_lead):
        # Hard-delete only newly created disposable records, never existing/demo records.
        customer = self.request("POST", "/api/customers", 201, json=self.customer_data(0, self.run + " disposable customer"))
        self.request("DELETE", f"/api/customers/{customer['id']}?expectedVersion={customer['version']}", 204)
        self.request("GET", f"/api/customers/{customer['id']}", 404)
        lead = self.request("POST", "/api/leads", 201, json=self.lead_data(0, self.run + " disposable lead"))
        self.request("DELETE", f"/api/leads/{lead['id']}?expectedVersion={lead['version']}", 204)
        self.request("GET", f"/api/leads/{lead['id']}", 404)
        task = self.request("POST", "/api/follow-ups", 201, json={"leadId": linked_lead["id"], "purpose": self.run + " archive verification",
            "dueAt": (datetime.now(timezone.utc) + timedelta(days=1)).isoformat()})
        self.request("DELETE", f"/api/follow-ups/{task['id']}?expectedVersion={task['version']}", 204)
        self.request("GET", f"/api/follow-ups/{task['id']}", 404)
        generated_document = self.quote_data(0, self.run + "-GENERATED")
        generated_document["customer"] = self.run + " disposable generated quote"
        generated = self.request("POST", "/api/quotations", 201, json=generated_document)
        generated = self.request("POST", f"/api/quotations/{generated['id']}/revisions", 201,
            data={"expectedVersion": str(generated["version"])},
            files={"file": (self.run + "-revision.pdf", self.fixture_pdf(generated_document), "application/pdf")})
        self.request("DELETE", f"/api/quotations/{generated['id']}?expectedVersion={generated['version']}", 204)
        self.request("GET", f"/api/quotations/{generated['id']}", 404)
        document = self.quote_data(4, self.run)
        document["customer"] = self.run + " disposable quote"
        quote = self.request("POST", "/api/quotations/upload", 201, data={"metadata": json.dumps(document)},
                             files={"file": (self.run + ".pdf", self.fixture_pdf(document), "application/pdf")})
        self.request("DELETE", f"/api/quotations/{quote['id']}?expectedVersion={quote['version']}", 204)
        self.request("GET", f"/api/quotations/{quote['id']}", 404)
        self.request("GET", f"/api/quotations/{quote['id']}/pdf", 404)
        self.archived_checks = {"followUpId": task["id"], "quotationIds": [generated["id"], quote["id"]]}

    def negative_checks(self, linked_lead):
        self.request("POST", "/api/leads", 422, json={**self.lead_data(0), "priority": "INVALID"})
        self.request("POST", "/api/customers", 422, json={"name": self.run, "contacts": []})
        self.request("POST", "/api/follow-ups", 422, json={"leadId": linked_lead["id"], "purpose": "Invalid timezone", "dueAt": "2026-11-04T10:00:00"})
        self.request("POST", "/api/quotations", 409, json=self.quote_data(0))
        invalid = self.quote_data(4, self.run + "-INVALID")
        self.request("POST", "/api/quotations/upload", 422, data={"metadata": json.dumps(invalid)},
                     files={"file": ("not-a-pdf.pdf", b"This is not PDF content", "application/pdf")})
        self.request("DELETE", f"/api/leads/{linked_lead['id']}?expectedVersion={linked_lead['version']}", 409)
        self.request("DELETE", f"/api/customers/{self.seeded['customers'][0]}?expectedVersion={self.request('GET', '/api/customers/' + self.seeded['customers'][0])['version']}", 409)
        quote = self.request("GET", f"/api/quotations/{self.seeded['quotations'][0]}")
        self.request("PUT", f"/api/quotations/{quote['id']}", 409, json={"expectedVersion": quote["version"] + 100, "status": "Accepted"})
        task = self.request("GET", f"/api/follow-ups/{self.seeded['followUps'][0]}")
        self.request("PUT", f"/api/follow-ups/{task['id']}", 409, json={"expectedVersion": task["version"] + 100, "notes": "Must not persist"})

    def verify_final(self):
        self.after = {}
        for module, path, label in [("customers", "/api/customers", "name"), ("leads", "/api/leads", "customer"),
                                    ("followUps", "/api/follow-ups", "purpose"), ("quotations", "/api/quotations", "number")]:
            rows = self.request("GET", path)
            ids = {x["id"] for x in rows}
            self.assert_true(self.original_ids[module].issubset(ids), f"Existing {module} records retained")
            self.assert_true(set(self.seeded[module]).issubset(ids), f"All five seeded {module} records remain visible")
            prefix = LABEL if module in {"leads", "customers"} else PREFIX
            count = sum(x[label].startswith(prefix) for x in rows)
            self.assert_true(count == 5, f"Exactly five labelled demo {module} records")
            self.after[module] = {"totalActive": len(rows), "demoActive": count}
        missing = set(self.routes) - self.covered
        self.assert_true(not missing, f"All {len(self.routes)} implemented API endpoints exercised successfully; missing={sorted(missing)}")

    def report(self, error=None):
        output = ROOT / "audit"
        output.mkdir(exist_ok=True)
        data = {"testedAt": datetime.now(timezone.utc).isoformat(), "api": API, "result": "FAIL" if error else "PASS",
                "error": str(error) if error else None, "checks": self.checks, "checkCount": len(self.checks),
                "passedChecks": sum(x["passed"] for x in self.checks), "seededIds": self.seeded,
                "counts": getattr(self, "after", {}), "archivedDeleteChecks": getattr(self, "archived_checks", {}),
                "coverage": [{"method": method, "path": path, "passed": (method, path) in self.covered}
                             for method, path in sorted(self.routes)],
                "pendingModules": ["Background notification delivery", "CRM record assignment permissions"],
                "notes": ["Only synthetic QA data was created/updated/deleted.", "Five active demo records are retained per implemented module.",
                          "DELETE checks archive a temporary follow-up and two temporary quotations per run; their histories remain stored by design.",
                          "Authentication and user-management permissions are tested separately in isolated databases, outside this CRM seed run.", "No email, SMS or other external messages were sent."]}
        (output / "API-TEST-REPORT.json").write_text(json.dumps(data, indent=2), encoding="utf-8")
        lines = ["# Live CRM API test report", "", f"Result: **{data['result']}**", f"Tested: {data['testedAt']}",
                 f"Checks: {data['passedChecks']}/{data['checkCount']}", f"Endpoint coverage: {len(self.covered & set(self.routes))}/{len(self.routes)} (including health)",
                 "", "## Visible test data", "", "| Module | Demo records | Total active records |", "| --- | --- | --- |"]
        lines += [f"| {module} | {count['demoActive']} | {count['totalActive']} |" for module, count in data["counts"].items()]
        lines += ["", "## Endpoint checks", "", "| Method | Endpoint | Result |", "| --- | --- | --- |"]
        lines += [f"| {x['method']} | `{x['path']}` | {'PASS' if x['passed'] else 'NOT COVERED'} |" for x in data["coverage"]]
        lines += ["", "## Notes", ""] + ["- " + note for note in data["notes"]]
        lines += ["", "Pending: " + ", ".join(data["pendingModules"]) + "."]
        if error:
            lines += ["", "Failure: " + str(error)]
        (output / "API-TEST-REPORT.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
        print(json.dumps({"result": data["result"], "passedChecks": data["passedChecks"], "checks": data["checkCount"],
                          "endpoints": len(self.covered & set(self.routes)), "totalEndpoints": len(self.routes),
                          "counts": data["counts"], "report": str(output / "API-TEST-REPORT.md")}), flush=True)


if __name__ == "__main__":
    verification = Verification()
    failure = None
    try:
        verification.execute()
    except Exception as error:
        failure = error
    finally:
        end_test_session(verification.client)
        verification.report(failure)
        verification.client.close()
    if failure:
        raise SystemExit(str(failure))
