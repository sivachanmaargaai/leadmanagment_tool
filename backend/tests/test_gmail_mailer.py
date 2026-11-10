import base64
import json
import os
import unittest
from email import policy
from email.parser import BytesParser
from unittest.mock import MagicMock, patch
from urllib.parse import parse_qs

os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
from pydantic import SecretStr, ValidationError
from app.core.config import Settings, settings
from app.services.mailer import send_otp_message


class GmailMailerTests(unittest.TestCase):
    def test_gmail_refreshes_over_https_and_sends_code_without_smtp(self):
        token_response, send_response = MagicMock(), MagicMock()
        token_response.__enter__.return_value.read.return_value = b'{"access_token":"fixture-access"}'
        send_response.__enter__.return_value.read.return_value = b'{"id":"fixture-message"}'
        with patch.object(settings, "MAIL_PROVIDER", "gmail"), patch.object(settings, "GMAIL_CLIENT_ID", "fixture-client"), \
                patch.object(settings, "GMAIL_CLIENT_SECRET", SecretStr("fixture-secret")), \
                patch.object(settings, "GMAIL_REFRESH_TOKEN", SecretStr("fixture-refresh")), \
                patch.object(settings, "GMAIL_SENDER", "sender@example.test"), \
                patch("app.services.mailer.urlopen", side_effect=[token_response, send_response]) as http, \
                patch("app.services.mailer.smtplib.SMTP") as smtp:
            send_otp_message("recipient@example.test", "012345", 10)
        smtp.assert_not_called()
        first, second = http.call_args_list
        self.assertEqual(first.args[0].full_url, "https://oauth2.googleapis.com/token")
        form = parse_qs(first.args[0].data.decode())
        self.assertEqual(form["grant_type"], ["refresh_token"])
        self.assertEqual(form["refresh_token"], ["fixture-refresh"])
        self.assertTrue(first.kwargs["context"].check_hostname)
        self.assertLessEqual(first.kwargs["timeout"], 30)
        self.assertEqual(second.args[0].full_url, "https://gmail.googleapis.com/gmail/v1/users/me/messages/send")
        self.assertEqual(second.args[0].get_header("Authorization"), "Bearer fixture-access")
        encoded = json.loads(second.args[0].data)["raw"]
        message = BytesParser(policy=policy.default).parsebytes(base64.urlsafe_b64decode(encoded))
        self.assertEqual(message["To"], "recipient@example.test")
        self.assertEqual(message["From"].addresses[0].addr_spec, "sender@example.test")
        self.assertIn("012345", message.get_content())
        self.assertNotIn("fixture-secret", message.get_content())

    def test_rejected_token_and_missing_acknowledgment_fail_closed(self):
        for raw in (b'{}', b'[]', b'invalid-json', b'x' * 32769):
            response = MagicMock()
            response.__enter__.return_value.read.return_value = raw
            with patch.object(settings, "MAIL_PROVIDER", "gmail"), patch("app.services.mailer.urlopen", return_value=response):
                with self.assertRaises((ValueError, RuntimeError)):
                    send_otp_message("recipient@example.test", "012345", 10)
        with patch.object(settings, "MAIL_PROVIDER", "gmail"), patch("app.services.mailer.google_request", side_effect=[{"access_token": "fixture"}, {}]):
            with self.assertRaises(ValueError):
                send_otp_message("recipient@example.test", "012345", 10)

    def test_google_errors_hide_provider_payloads_and_do_not_retry(self):
        from io import BytesIO
        from urllib.error import HTTPError
        from app.services.mailer import google_request, MailDeliveryError
        failure = HTTPError("https://oauth2.googleapis.com/token", 400, "fixture-private-provider-error", {}, BytesIO(b'{"private":"fixture-secret"}'))
        with patch("app.services.mailer.urlopen", side_effect=failure) as http:
            with self.assertRaises(MailDeliveryError) as caught:
                google_request("https://oauth2.googleapis.com/token", b"fixture", "application/x-www-form-urlencoded")
        self.assertEqual(str(caught.exception), "Gmail delivery failed")
        self.assertNotIn("fixture", str(caught.exception))
        self.assertEqual(http.call_count, 1)

    def test_gmail_configuration_needs_all_credentials_and_valid_sender(self):
        values = dict(DATABASE_URL="sqlite://", PASSWORD_RECOVERY_ENABLED=True, MAIL_PROVIDER="gmail",
            GMAIL_CLIENT_ID="fixture-client", GMAIL_CLIENT_SECRET="fixture-secret", GMAIL_REFRESH_TOKEN="fixture-refresh",
            GMAIL_SENDER="sender@example.test", ENVIRONMENT="production", COOKIE_SECURE=True,
            ALLOWED_ORIGINS=["https://crm.example.test"])
        self.assertEqual(Settings(_env_file=None, **values).MAIL_PROVIDER, "gmail")
        for key in ("GMAIL_CLIENT_ID", "GMAIL_CLIENT_SECRET", "GMAIL_REFRESH_TOKEN", "GMAIL_SENDER"):
            with self.assertRaises(ValidationError) as caught:
                Settings(_env_file=None, **{**values, key: ""})
            self.assertNotIn("fixture-secret", str(caught.exception))
            self.assertNotIn("fixture-refresh", str(caught.exception))
        with self.assertRaises(ValidationError):
            Settings(_env_file=None, **{**values, "GMAIL_SENDER": "bad\r\nsender@example.test"})
