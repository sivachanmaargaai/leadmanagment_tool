import smtplib
import ssl
from email.message import EmailMessage
from email.utils import formataddr

from app.core.config import settings


def send_reset_message(recipient, link, minutes):
    message = EmailMessage()
    message["Subject"] = "Reset your ENGEN CRM password"
    message["From"] = formataddr((settings.SMTP_FROM_NAME, settings.SMTP_FROM))
    message["To"] = recipient
    message.set_content(
        f"A password reset was requested for your ENGEN CRM account.\n\n"
        f"Open this link to choose a new password:\n{link}\n\n"
        f"This link expires in {minutes} minutes and can be used once. "
        "Never share this link or your password.\n\n"
        "If you did not request this, ignore the email. Your password has not changed.\n"
    )
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
