"""Read-only checks for five report scenarios against the running local API."""
import json
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path

import httpx
from api_auth import authenticate_client, end_test_session

ROOT = Path(__file__).resolve().parents[1]
PREFIXES = ("[qa test]", "qa-demo-", "qa-check-")
IST = timezone(timedelta(hours=5, minutes=30))


def is_test(*values):
    return any(str(value or "").strip().lower().startswith(PREFIXES) for value in values)


def main():
    checks = []
    scenarios = []
    def check(condition, name):
        checks.append({"check": name, "passed": bool(condition)})
        if not condition:
            raise AssertionError(name)
    with httpx.Client(base_url="http://127.0.0.1:8000", timeout=30) as client:
        def get(kind, **params):
            response = client.get("/api/reports/" + kind, params=params)
            check(response.status_code == 200, f"GET /api/reports/{kind} {params} returns 200")
            return response.json()
        try:
            authenticate_client(client)
            leads = client.get("/api/leads").raise_for_status().json()
            quotes = client.get("/api/quotations").raise_for_status().json()
            followups = client.get("/api/follow-ups").raise_for_status().json()
            # 1. All four endpoints must reconcile to the live source APIs.
            summary = get("summary", includeTestData="true")
            lead_report = get("leads", includeTestData="true")
            sale_report = get("sales", includeTestData="true")
            follow_report = get("follow-ups", includeTestData="true")
            check(summary["totals"]["totalLeads"] == len(leads) == len(lead_report["rows"]), "Live lead totals reconcile")
            check(summary["totals"]["totalQuotations"] == len(quotes) == len(sale_report["rows"]), "Live quotation totals reconcile")
            check(follow_report["summary"]["total"] == len(followups) == len(follow_report["rows"]), "Live follow-up totals reconcile")
            won, lost = sum(x["status"] == "Won" for x in leads), sum(x["status"] == "Lost" for x in leads)
            check(summary["totals"]["conversionRate"] == (round(100 * won / (won + lost), 2) if won + lost else 0), "Closed-lead conversion formula")
            scenarios.append({"name": "1. All-time reports reconcile with source APIs", "passed": True})
            # 2. Synthetic records are hidden by default, shown only when requested.
            hidden = get("summary")
            check(hidden["totals"]["totalLeads"] == sum(not is_test(x["customer"]) for x in leads), "Default summary excludes labelled test leads")
            for kind in ["leads", "sales", "follow-ups"]:
                rows = get(kind)["rows"]
                check(all(not is_test(x["customer"], x.get("number"), x.get("purpose")) for x in rows), f"Default {kind} excludes synthetic rows")
            scenarios.append({"name": "2. Include test data toggle", "passed": True})
            # 3. Each division must reconcile independently across all modules.
            for division in ["MMC", "nemilink", "ClearCode Labs", "ENGEN", "Visotonics", "Overview"]:
                scoped = get("summary", includeTestData="true", division=division)
                check(scoped["totals"]["totalLeads"] == sum(x["division"] == division for x in leads), f"{division} lead total")
                for kind in ["leads", "sales", "follow-ups"]:
                    check(all(x["division"] == division for x in get(kind, includeTestData="true", division=division)["rows"]), f"{division} {kind} scope")
            scenarios.append({"name": "3. Division filters for all six divisions", "passed": True})
            # 4. Inclusive date boundaries use each report's documented IST date basis.
            today = datetime.now(IST).date().isoformat()
            expected = sum(datetime.fromisoformat(x["createdAt"].replace("Z", "+00:00")).astimezone(IST).date().isoformat() == today for x in leads)
            check(len(get("leads", includeTestData="true", startDate=today, endDate=today)["rows"]) == expected, "Lead created-date filtering in IST")
            check(len(get("sales", includeTestData="true", startDate=today, endDate=today)["rows"]) == sum(x["date"] == today for x in quotes), "Quotation issue-date filtering")
            due_today = sum(datetime.fromisoformat(x["dueAt"].replace("Z", "+00:00")).astimezone(IST).date().isoformat() == today for x in followups)
            check(len(get("follow-ups", includeTestData="true", startDate=today, endDate=today)["rows"]) == due_today, "Follow-up due-date filtering in IST")
            scenarios.append({"name": "4. IST date boundaries and module-specific dates", "passed": True})
            # 5. Status scopes, accepted financial buckets and expected validation errors.
            for kind, status in [("leads", "Won"), ("sales", "Expired"), ("follow-ups", "Completed")]:
                check(all(x["status"] == status for x in get(kind, includeTestData="true", status=status)["rows"]), f"{kind} status filter")
            expected_values = {}
            for quote in quotes:
                if quote["status"] == "Accepted":
                    for billing, amount in quote["totals"].items():
                        key = (quote["currency"], billing)
                        expected_values[key] = expected_values.get(key, Decimal("0")) + Decimal(str(amount["total"]))
            actual_values = {(x["currency"], x["billing"]): Decimal(str(x["total"])) for x in summary["acceptedValue"]}
            check(expected_values == actual_values, "Accepted amounts remain separate by currency and billing period")
            for kind, params in [("summary", {"startDate": "2026-11-20", "endDate": "2026-11-01"}), ("leads", {"division": "Invalid"}), ("sales", {"status": "Won"}), ("follow-ups", {"status": "Sent"})]:
                check(client.get("/api/reports/" + kind, params=params).status_code == 422, f"Invalid {kind} filters rejected")
            scenarios.append({"name": "5. Status, financial calculations and invalid inputs", "passed": True})
            failure = None
        except Exception as error:
            failure = str(error)
        finally:
            end_test_session(client)
        report = {"testedAt": datetime.now(timezone.utc).isoformat(), "result": "FAIL" if failure else "PASS", "error": failure,
                  "scenarios": scenarios, "checks": checks, "passedChecks": sum(x["passed"] for x in checks), "checkCount": len(checks),
                  "dataChanged": False, "browserVerification": "Not completed: Computer Use stopped because it could not verify the current Windows browser URL."}
        out = ROOT / "audit"
        out.mkdir(exist_ok=True)
        (out / "REPORTS-TEST-REPORT.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
        lines = ["# Reports test report", "", f"Result: **{report['result']}**", f"Checks: {report['passedChecks']}/{report['checkCount']}", "", "Read-only tests against the running API and existing sample records. No data was modified.", ""]
        lines += [f"- PASS: {x['name']}" for x in scenarios]
        lines += ["", "Browser verification: " + report["browserVerification"]]
        if failure:
            lines += ["", "Failure: " + failure]
        (out / "REPORTS-TEST-REPORT.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
        print(json.dumps({"result": report["result"], "scenarios": len(scenarios), "passedChecks": report["passedChecks"], "checks": report["checkCount"], "error": failure}))
        if failure:
            raise SystemExit(1)


if __name__ == "__main__":
    main()
