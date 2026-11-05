"""Interactive authentication for local QA scripts; never save credentials or tokens."""
import os
from getpass import getpass


def authenticate_client(client):
    try:
        email = os.environ.get("CRM_TEST_EMAIL") or input("CRM login email: ")
        password = getpass("CRM password (not saved): ")
    except (KeyboardInterrupt, EOFError):
        raise SystemExit("Sign-in cancelled. Run this script in an interactive terminal.") from None
    client.headers["X-CRM-Request"] = "1"
    result = client.post("/api/auth/login", json={"email": email, "password": password})
    password = None
    if result.status_code != 200 or not result.json().get("accessToken"):
        raise SystemExit(f"CRM sign-in failed ({result.status_code}); no credentials were saved.")
    client.headers["Authorization"] = "Bearer " + result.json()["accessToken"]


def end_test_session(client):
    if "Authorization" not in client.headers:
        return
    try:
        result = client.post("/api/auth/logout")
        if result.status_code != 204:
            print("The QA session could not be signed out. Its normal expiry still applies.")
    except Exception:
        print("The QA session could not be signed out. Its normal expiry still applies.")
    client.headers.pop("Authorization", None)
