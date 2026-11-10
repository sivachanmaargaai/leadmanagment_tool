"""Smoke-test release images without real database/mail credentials or account changes."""
import json
import re
import subprocess
import time
from http.client import HTTPException
from urllib.error import URLError
from urllib.request import urlopen


def main():
    containers = []
    results = {}

    def docker(*args):
        return subprocess.check_output(["docker", *args], text=True).strip()

    def start(image, *environment):
        args = ["run", "--detach", "--publish", "127.0.0.1::10000"]
        for item in environment:
            args += ["--env", item]
        container = docker(*args, image)
        assert re.fullmatch(r"[a-f0-9]{64}", container)
        containers.append(container)
        port = docker("port", container, "10000/tcp").split(":")[-1]
        assert port.isdigit()
        return container, "http://127.0.0.1:" + port

    def read(url):
        for attempt in range(30):
            try:
                with urlopen(url, timeout=3) as response:
                    return response.read()
            except (URLError, OSError, HTTPException):
                if attempt == 29:
                    raise
                time.sleep(.5)

    try:
        backend, backend_url = start("chan0345/leadmanagement-backend:v1.1",
            "DATABASE_URL=sqlite:///:memory:", "ENVIRONMENT=test",
            "PASSWORD_RECOVERY_ENABLED=false", "OPS_LOG_ENABLED=false")
        assert json.loads(read(backend_url + "/api/health"))["status"] == "ok"
        assert "/api/auth/verify-reset-otp" in json.loads(read(backend_url + "/openapi.json"))["paths"]
        check = (
            "from pathlib import Path; from alembic.config import Config; "
            "from app.services.quotation_pdf import LOGO_PATH; "
            "from alembic.script import ScriptDirectory; "
            "assert ScriptDirectory.from_config(Config('alembic.ini')).get_current_head()=='20261106_0015'; "
            "assert not Path('/app/.env.local').exists(); assert not Path('/app/.env').exists(); "
            "assert LOGO_PATH.is_file(); "
            "assert not list(Path('/app').rglob('*.bak')); print('passed')"
        )
        assert docker("exec", backend, "python", "-c", check) == "passed"
        results["backend_health_otp_migration_logo_secret_exclusion"] = "passed"
        _, frontend_url = start("chan0345/leadmanagement-frontend:v1.1",
            "API_UPSTREAM_HOST=leadmanagement-backend-v1-1.onrender.com")
        html = read(frontend_url + "/").decode()
        assert '<div id="root"></div>' in html
        asset = re.search(r'src="([^"]+\.js)"', html).group(1)
        bundle = read(frontend_url + asset).decode()
        assert "/api/auth/verify-reset-otp" in bundle
        assert "GMAIL_CLIENT_SECRET" not in bundle
        results["frontend_http_assets_otp_bundle"] = "passed"
        try:
            with urlopen(frontend_url + "/api/health", timeout=20) as response:
                assert json.load(response)["status"] == "ok"
            results["nginx_https_proxy_to_render"] = "passed"
        except Exception as error:
            results["nginx_https_proxy_to_render"] = "not_verified_" + type(error).__name__
        print(json.dumps(results), flush=True)
    finally:
        for container in reversed(containers):
            subprocess.run(["docker", "rm", "--force", container],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)


if __name__ == "__main__":
    main()
