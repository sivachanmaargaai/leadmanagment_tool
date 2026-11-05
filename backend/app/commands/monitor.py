import json
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import urlopen
from app.core.config import settings
from app.services.operations import operations_status


def main():
    result = operations_status()
    ready = False
    status = None
    try:
        base = urlsplit(settings.OPS_HEALTH_BASE_URL)
        if base.scheme not in {"http", "https"} or not base.netloc or base.username or base.password or base.query or base.fragment:
            raise ValueError("Invalid monitoring base URL")
        with urlopen(settings.OPS_HEALTH_BASE_URL.rstrip("/") + "/api/ready", timeout=5) as response:
            status = response.status
            ready = status == 200 and json.loads(response.read(1024)).get("status") == "ready"
    except HTTPError as error:
        status = error.code
    except (URLError, OSError, ValueError):
        pass
    result["api"] = {"ready": ready, "statusCode": status}
    result["metrics"] = {"scope": "server-metrics-available-in-owner-panel"}
    if not ready:
        result["issues"].append("api-not-ready")
        result["status"] = "critical"
    print(json.dumps(result, sort_keys=True))
    raise SystemExit({"ok": 0, "warning": 1, "critical": 2}[result["status"]])


if __name__ == "__main__":
    main()
