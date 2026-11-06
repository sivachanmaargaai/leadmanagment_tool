"""Send ENGEN CRM account recovery mail using SMTP or Gmail OAuth2."""
import base64
import json
import smtplib
import ssl
from email.message import EmailMessage
from email.utils import formataddr
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from app.core.config import settings


class MailDeliveryError(RuntimeError):
    """Safe mail-delivery error without provider response bodies or credentials."""


def _send_via_gmail(message):
    # Gmail API requires a user-authorized refresh token with gmail.send scope.
    form = urlencode({
        "client_id": settings.GMAIL_CLIENT_ID,
        "client_secret": settings.GMAIL_CLIENT_SECRET.get_secret_value(),
        "refresh_token": settings.GMAIL_REFRESH_TOKEN.get_secret_value(),
        "grant_type": "refresh_token",
    }).encode("utf-8")
    token_request = Request(
        "https://oauth2.googleapis.com/token", data=form,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        method="POST",
    )
    try:
        with urlopen(token_request, timeout=settings.SMTP_TIMEOUT_SECONDS) as response:
            token_response = json.load(response)
        access_token = token_response.get("access_token")
        if not isinstance(access_token, str) or not access_token:
            raise MailDeliveryError("Gmail did not return an access token")
        raw_message = base64.urlsafe_b64encode(message.as_bytes()).decode("ascii").rstrip("=")
        send_request = Request(
            "https://gmail.googleapis.com/gmail/v1/users/me/messages/send",
            data=json.dumps({"raw": raw_message}).encode("utf-8"),
            headers={"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"},
            method="POST",
        )
        with urlopen(send_request, timeout=settings.SMTP_TIMEOUT_SECONDS) as response:
            result = json.load(response)
        if not result.get("id"):
            raise MailDeliveryError("Gmail did not confirm message submission")
    except (HTTPError, URLError, TimeoutError, OSError, ValueError, KeyError) as exc:
        # Never propagate Google error payloads: they may contain private details.
        raise MailDeliveryError("Gmail delivery failed") from None


def _send_via_smtp(message):
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
    if settings.MAIL_PROVIDER == "gmail":
        _send_via_gmail(message)
    else:
        _send_via_smtp(message)
