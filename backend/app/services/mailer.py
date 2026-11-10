"""Send ENGEN CRM account recovery mail using SMTP or Gmail OAuth2."""
import base64
import json
import smtplib
import ssl
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from email.message import EmailMessage
from email.utils import formataddr
from urllib.error import HTTPError

from app.core.config import settings


class MailDeliveryError(RuntimeError):
    """Safe mail-delivery error without provider response bodies or credentials."""


def google_request(url, body, content_type, bearer=None):
    headers = {"Content-Type": content_type}
    if bearer:
        headers["Authorization"] = "Bearer " + bearer
    request = Request(url, data=body, headers=headers, method="POST")
    # Fixed HTTPS endpoints, verified TLS, bounded reads and timeouts. Never log responses.
    try:
        with urlopen(request, timeout=settings.SMTP_TIMEOUT_SECONDS, context=ssl.create_default_context()) as response:
            raw = response.read(32769)
            if len(raw) > 32768:
                raise ValueError("Mail provider response too large")
            result = json.loads(raw)
            if not isinstance(result, dict):
                raise ValueError("Invalid mail provider response")
            return result
    except HTTPError as error:
        error.close()
        raise MailDeliveryError("Gmail delivery failed") from None
    except (OSError, ValueError):
        raise MailDeliveryError("Gmail delivery failed") from None


def send_message(message):
    if settings.MAIL_PROVIDER == "gmail":
        token = google_request("https://oauth2.googleapis.com/token", urlencode({
            "client_id": settings.GMAIL_CLIENT_ID,
            "client_secret": settings.GMAIL_CLIENT_SECRET.get_secret_value(),
            "refresh_token": settings.GMAIL_REFRESH_TOKEN.get_secret_value(),
            "grant_type": "refresh_token",
        }).encode("ascii"), "application/x-www-form-urlencoded")
        access = token.get("access_token")
        if not isinstance(access, str) or not access or any(c in access for c in "\r\n"):
            raise ValueError("Mail provider did not return an access token")
        result = google_request("https://gmail.googleapis.com/gmail/v1/users/me/messages/send",
            json.dumps({"raw": base64.urlsafe_b64encode(message.as_bytes()).decode("ascii")}).encode("utf-8"),
            "application/json", bearer=access)
        if not result.get("id"):
            raise ValueError("Mail provider did not acknowledge delivery")
        return
    context = ssl.create_default_context()
    smtp_class = smtplib.SMTP_SSL if settings.SMTP_SECURITY == "ssl" else smtplib.SMTP
    options = {"host": settings.SMTP_HOST, "port": settings.SMTP_PORT, "timeout": settings.SMTP_TIMEOUT_SECONDS}
    if settings.SMTP_SECURITY == "ssl":
        options["context"] = context
    with smtp_class(**options) as server:
        server.ehlo()
        if settings.SMTP_SECURITY == "starttls":
            server.starttls(context=context)
            server.ehlo()
        server.login(settings.SMTP_USERNAME, settings.SMTP_PASSWORD.get_secret_value())
        server.send_message(message)


def send_otp_message(recipient, code, minutes):
    message = EmailMessage()
    message["Subject"] = "Your ENGEN CRM password reset code"
    sender = settings.GMAIL_SENDER if settings.MAIL_PROVIDER == "gmail" else settings.SMTP_FROM
    message["From"] = formataddr((settings.SMTP_FROM_NAME, sender))
    message["To"] = recipient
    message.set_content(
        f"Your ENGEN CRM password reset code is: {code}\n\n"
        f"This code expires in {minutes} minutes. Enter it only in ENGEN CRM. "
        "Never share this code or your password.\n\n"
        "If you did not request this, ignore this email. Your password has not changed.\n"
    )
    send_message(message)


def send_reset_message(recipient, link, minutes):
    message = EmailMessage()
    message["Subject"] = "Reset your ENGEN CRM password"
    sender = settings.GMAIL_SENDER if settings.MAIL_PROVIDER == "gmail" else settings.SMTP_FROM
    message["From"] = formataddr((settings.SMTP_FROM_NAME, sender))
    message["To"] = recipient
    message.set_content(
        "A password reset was requested for your ENGEN CRM account.\n\n"
        f"Open this link to choose a new password:\n{link}\n\n"
        f"This link expires in {minutes} minutes and can be used once. "
        "Never share this link or your password.\n\n"
        "If you did not request this, ignore the email. Your password has not changed.\n"
    )
    send_message(message)
