import asyncio
from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

os.environ["DATABASE_URL"] = "sqlite:///:memory:"
from app.core.config import settings
from app.core.observability import Metrics, ObservabilityMiddleware
from app.services.backup_crypto import decrypt_file, encrypt_file, load_key, sign_manifest
from app.services.backups import backup_status, manifest_path, pg_environment, pg_url, read_manifest, save_manifest
from app.services.backups import prune_backups
from app.services.operations import operations_status
import test_crm_access as fixtures


class BackupCryptoTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.root = Path(self.directory.name)
        self.setting = patch.object(settings, "OPS_DIRECTORY", self.root)
        self.setting.start()
        (self.root / "keys").mkdir()
        (self.root / "backups").mkdir()
        self.key = load_key(self.root / "keys" / "backup.key", create=True)

    def tearDown(self):
        self.setting.stop()
        self.directory.cleanup()

    def manifest(self):
        backup_id = "engen_20261105T010000Z_" + "a" * 12
        archive = self.root / "backups" / (backup_id + ".dump.enc")
        archive.write_bytes(b"encrypted fixture")
        data = {"format": "engen-backup-v1", "id": backup_id, "archive": archive.name,
                "bytes": archive.stat().st_size, "createdAt": datetime.now(timezone.utc).isoformat(), "restoreVerifiedAt": None}
        save_manifest(data, self.key)
        return data

    def test_streaming_encryption_roundtrip_tamper_rejection_and_existing_target_safety(self):
        source, encrypted, restored = self.root / "input", self.root / "encrypted", self.root / "restored"
        payload = b"private customer and PDF content" * 50000
        source.write_bytes(payload)
        encrypt_file(source, encrypted, self.key)
        self.assertNotIn(b"private customer", encrypted.read_bytes())
        decrypt_file(encrypted, restored, self.key)
        self.assertEqual(restored.read_bytes(), payload)
        with self.assertRaises(FileExistsError):
            decrypt_file(encrypted, restored, self.key)
        self.assertEqual(restored.read_bytes(), payload)
        restored.unlink()
        content = bytearray(encrypted.read_bytes())
        content[len(content) // 2] ^= 1
        encrypted.write_bytes(content)
        with self.assertRaises(Exception):
            decrypt_file(encrypted, restored, self.key)
        self.assertFalse(restored.exists())

    def test_key_stays_stable_manifest_tamper_and_traversal_are_rejected(self):
        self.assertEqual(load_key(self.root / "keys" / "backup.key", create=True), self.key)
        data = self.manifest()
        read_manifest(data["id"], self.key)
        raw = json.loads(manifest_path(data["id"]).read_text())
        raw["archive"] = "../../outside"
        manifest_path(data["id"]).write_text(json.dumps(raw))
        with self.assertRaises(ValueError):
            read_manifest(data["id"], self.key)
        with self.assertRaises(ValueError):
            manifest_path("../invalid")

    def test_fresh_stale_missing_status_does_not_create_a_key(self):
        self.assertEqual(backup_status()["status"], "missing-or-invalid")
        data = self.manifest()
        self.assertEqual(backup_status()["status"], "fresh")
        data["createdAt"] = (datetime.now(timezone.utc) - timedelta(hours=48)).isoformat()
        save_manifest(data, self.key)
        self.assertEqual(backup_status()["status"], "stale")
        (self.root / "keys" / "backup.key").unlink()
        self.assertEqual(backup_status()["status"], "not-configured")
        self.assertFalse((self.root / "keys" / "backup.key").exists())

    def test_postgres_credentials_are_not_in_arguments_or_persistent_environment(self):
        url = pg_url("postgresql+psycopg://crm:p%3Aa%5Css@localhost:5432/crm")
        with pg_environment(url, self.root) as env:
            self.assertNotIn("PGPASSWORD", env)
            self.assertEqual(env["PGDATABASE"], "crm")
            self.assertTrue(Path(env["PGPASSFILE"]).exists())
        self.assertFalse((self.root / "pgpass").exists())
        with self.assertRaises(ValueError):
            pg_url("sqlite://")

    def test_retention_preserves_last_verified_copy_and_unrelated_files(self):
        original = self.manifest()
        for i in range(4):
            data = {**original, "id": "engen_20261105T010000Z_" + f"{i:012x}",
                    "createdAt": (datetime.now(timezone.utc) - timedelta(hours=i)).isoformat(),
                    "restoreVerifiedAt": datetime.now(timezone.utc).isoformat() if i == 3 else None}
            data["archive"] = data["id"] + ".dump.enc"
            (self.root / "backups" / data["archive"]).write_bytes(b"encrypted fixture")
            save_manifest(data, self.key)
        unrelated = self.root / "backups" / "keep-me.txt"
        unrelated.write_text("user file")
        with patch.object(settings, "BACKUP_RETENTION_COUNT", 2):
            prune_backups(self.key)
        self.assertTrue(unrelated.exists())
        self.assertTrue((self.root / "backups" / ("engen_20261105T010000Z_" + f"{3:012x}" + ".json")).exists())
        self.assertFalse((self.root / "backups" / ("engen_20261105T010000Z_" + f"{2:012x}" + ".json")).exists())


class MonitoringApiTests(unittest.TestCase):
    setUp = fixtures.CrmAccessTests.setUp
    tearDown = fixtures.CrmAccessTests.tearDown

    def test_owner_only_operations_and_safe_public_readiness(self):
        summary = {"status": "warning", "issues": ["backup-not-configured"], "database": {"reachable": True, "schemaCurrent": True}}
        with patch("app.routers.operations.operations_status", return_value=summary):
            for number, expected in [(0, 200), (1, 403), (2, 403), (3, 403)]:
                result = self.client.get("/api/ops/status", headers=self.headers[number])
                self.assertEqual(result.status_code, expected)
                self.assertIn("x-request-id", result.headers)
            self.assertEqual(self.client.get("/api/ops/status", headers={"Authorization": ""}).status_code, 401)
        for ok, expected in [(True, 200), (False, 503)]:
            with patch("app.routers.operations.probe_database", return_value={"reachable": ok, "schemaCurrent": ok}):
                result = self.client.get("/api/ready", headers={"Authorization": ""})
                self.assertEqual(result.status_code, expected)
                self.assertEqual(set(result.json()), {"status"})

    def test_operations_reports_unconfigured_backups_and_database_failure(self):
        with patch("app.services.operations.probe_database", return_value={"reachable": True, "schemaCurrent": True}), patch("app.services.operations.backup_status", return_value={"status": "not-configured", "restoreVerifiedAt": None}):
            self.assertEqual(operations_status()["status"], "warning")
        with patch("app.services.operations.probe_database", return_value={"reachable": False, "schemaCurrent": False}), patch("app.services.operations.backup_status", return_value={"status": "not-configured"}):
            self.assertEqual(operations_status()["status"], "critical")


class RequestLoggingTests(unittest.TestCase):
    def test_logs_templates_only_and_handle_unexpected_errors_without_secret_messages(self):
        async def endpoint(scope, receive, send):
            raise RuntimeError("password=private-secret token=private-token")
        async def receive():
            return {"type": "http.request", "body": b"private-body"}
        sent = []
        async def send(message):
            sent.append(message)
        scope = {"type": "http", "method": "POST", "path": "/api/private-customer", "query_string": b"token=private-token", "headers": [(b"authorization", b"private-auth"), (b"x-request-id", b"bad\r\ninjected")]}
        with self.assertLogs("engen.operations", level="INFO") as logs:
            asyncio.run(ObservabilityMiddleware(endpoint)(scope, receive, send))
        text = " ".join(logs.output)
        for secret in ["private-secret", "private-token", "private-body", "private-customer", "private-auth", "injected"]:
            self.assertNotIn(secret, text)
        event = json.loads(logs.records[-1].message)
        self.assertEqual(event["errorType"], "RuntimeError")
        self.assertEqual(sent[0]["status"], 500)
        self.assertIn("requestId", json.loads(sent[1]["body"]))

    def test_metrics_are_bounded_and_capture_errors_rate_limits_and_latency(self):
        metrics = Metrics()
        for i in range(300):
            metrics.record(f"route-{i}", 500 if i == 0 else 429, 3)
        snapshot = metrics.snapshot()
        self.assertLessEqual(len(snapshot["routes"]), 128)
        self.assertEqual(snapshot["serverErrors"], 1)
        self.assertEqual(snapshot["rateLimited"], 299)
        self.assertEqual(snapshot["slowRequests"], 300)

    def test_monitor_cli_detects_offline_api_without_claiming_own_metrics_are_server_metrics(self):
        from app.commands.monitor import main
        from urllib.error import URLError
        with patch("app.commands.monitor.operations_status", return_value={"status": "ok", "issues": [], "metrics": {"requests": 0}}), patch("app.commands.monitor.urlopen", side_effect=URLError("private endpoint")), patch("builtins.print") as output:
            with self.assertRaises(SystemExit) as stopped:
                main()
        self.assertEqual(stopped.exception.code, 2)
        data = json.loads(output.call_args.args[0])
        self.assertFalse(data["api"]["ready"])
        self.assertEqual(data["status"], "critical")
        self.assertNotIn("requests", data["metrics"])
