import os
import tempfile
from pathlib import Path
import unittest
from unittest.mock import patch

os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
from pydantic import ValidationError
from app.core.config import Settings, load_settings


class EnvironmentConfigTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.local = Path(self.directory.name) / ".env.local"
        self.local.write_text('DATABASE_URL=postgresql://local_user:fixture-only@localhost:5432/local_crm\nCOOKIE_SECURE=false\n', encoding="utf-8")

    def tearDown(self):
        self.directory.cleanup()

    def test_local_file_is_loaded_independently_of_working_directory(self):
        with patch.dict(os.environ, {}, clear=True):
            settings = load_settings(self.local.resolve())
        self.assertEqual(settings.ENVIRONMENT, "development")
        self.assertEqual(settings.DATABASE_URL, "postgresql+psycopg://local_user:fixture-only@localhost:5432/local_crm")
        self.assertFalse(settings.COOKIE_SECURE)

    def test_legacy_env_is_not_a_fallback_and_missing_local_credentials_fail(self):
        legacy = self.local.parent / ".env"
        legacy.write_text("DATABASE_URL=postgresql://fixture:fixture@remote.invalid/live", encoding="utf-8")
        self.local.unlink()
        with patch.dict(os.environ, {}, clear=True), self.assertRaises(ValidationError):
            load_settings(self.local)

    def test_process_environment_wins_and_tests_ignore_local_files(self):
        with patch.dict(os.environ, {"DATABASE_URL": "sqlite:///:memory:"}, clear=True):
            self.assertEqual(load_settings(self.local).DATABASE_URL, "sqlite:///:memory:")
        self.local.write_text("NOT_A_VALID_ENVIRONMENT=ignored\nDATABASE_URL=invalid", encoding="utf-8")
        with patch.dict(os.environ, {"ENVIRONMENT": "test", "DATABASE_URL": "sqlite:///:memory:"}, clear=True):
            self.assertEqual(load_settings(self.local).ENVIRONMENT, "test")

    def test_render_uses_only_dashboard_environment_and_psycopg3(self):
        cloud = {"RENDER": "true", "DATABASE_URL": "postgres://render_user:fixture-only@render-db.invalid/live_crm",
                 "COOKIE_SECURE": "true", "ALLOWED_ORIGINS": '["https://crm.example.test"]'}
        with patch.dict(os.environ, cloud, clear=True):
            settings = load_settings(self.local)
        self.assertEqual(settings.ENVIRONMENT, "production")
        self.assertTrue(settings.COOKIE_SECURE)
        self.assertEqual(settings.ALLOWED_ORIGINS, ["https://crm.example.test"])
        self.assertEqual(settings.DATABASE_URL, "postgresql+psycopg://render_user:fixture-only@render-db.invalid/live_crm")

    def test_render_cannot_run_with_local_cookie_policy(self):
        with patch.dict(os.environ, {"RENDER": "true", "DATABASE_URL": "sqlite://"}, clear=True), self.assertRaises(ValidationError):
            load_settings(self.local)
        with patch.dict(os.environ, {"RENDER": "true", "ENVIRONMENT": "development"}, clear=True), self.assertRaisesRegex(ValueError, "ENVIRONMENT=production"):
            load_settings(self.local)

    def test_remote_development_requires_explicit_opt_in_and_errors_hide_secrets(self):
        values = {"DATABASE_URL": "postgresql://fixture:do-not-print-this@remote.invalid/live"}
        with patch.dict(os.environ, values, clear=True):
            with self.assertRaises(ValidationError) as caught:
                load_settings(self.local)
            self.assertNotIn("do-not-print-this", str(caught.exception))
            self.assertIn("local database", str(caught.exception))
        with patch.dict(os.environ, {**values, "ALLOW_REMOTE_DEVELOPMENT_DATABASE": "true"}, clear=True):
            self.assertTrue(load_settings(self.local).ALLOW_REMOTE_DEVELOPMENT_DATABASE)

    def test_local_file_cannot_select_production_mode(self):
        self.local.write_text(self.local.read_text(encoding="utf-8") + "ENVIRONMENT=production\n", encoding="utf-8")
        with patch.dict(os.environ, {}, clear=True):
            self.assertEqual(load_settings(self.local).ENVIRONMENT, "development")
