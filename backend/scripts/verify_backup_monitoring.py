"""Backup/restore disposable PostgreSQL data only; leave real backup configuration untouched."""
from datetime import timedelta
import hashlib
from pathlib import Path
import re
import shutil
import sys
import tempfile
from unittest.mock import patch
from uuid import uuid4

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import sessionmaker
from app.core.config import settings
from app.core.security import now, passwords
from app.db.database import get_db
from app.main import app
from app.models.user import User, AuthSession, AccessToken, RefreshToken
from app.models.password_reset import PasswordResetToken
from app.models.lead import Lead
from app.models.customer import Customer
from app.models.quotation import Quotation, QuotationFile
from app.routers.quotations import snapshot
from app.schemas.quotation import QuotationDocument
from app.services.quotation_pdf import generate_pdf
from app.services.backups import backup_status, create_backup, read_manifest, restore_check
from app.services.backup_crypto import load_key
from app.services.ops_files import root_path


def main():
    source = make_url(settings.DATABASE_URL)
    assert source.get_backend_name() == "postgresql"
    name = "engen_backup_qa_" + uuid4().hex
    assert re.fullmatch(r"engen_backup_qa_[a-f0-9]{32}", name)
    assert name != source.database
    maintenance = create_engine(source.set(database="postgres"), isolation_level="AUTOCOMMIT", connect_args={"connect_timeout": 5})
    created = False
    qa_engine = None
    recovered_name = None
    backend = Path(__file__).resolve().parents[1]
    area = backend / "var"
    area.mkdir(exist_ok=True)
    directory = Path(tempfile.mkdtemp(prefix="backup-qa-", dir=area)).resolve()
    assert directory.is_relative_to(area.resolve()) and directory.name.startswith("backup-qa-")
    try:
        with maintenance.connect() as connection:
            connection.exec_driver_sql('CREATE DATABASE "' + name + '" TEMPLATE template0')
            created = True
        url = source.set(database=name)
        qa_engine = create_engine(url, connect_args={"connect_timeout": 5})
        config = Config(str(backend / "alembic.ini"))
        config.set_main_option("script_location", str(backend / "migrations"))
        with qa_engine.begin() as connection:
            config.attributes["connection"] = connection
            command.upgrade(config, "head")
        factory = sessionmaker(bind=qa_engine)
        with factory() as db:
            user = User(email="qa-backup@example.test", name="QA Owner", role="Admin", is_owner=True, admin_slot=1, password_hash=passwords.hash("QaBackup123"))
            db.add(user)
            db.flush()
            session = AuthSession(user_id=user.id, expires_at=now() + timedelta(days=1))
            db.add(session)
            db.flush()
            db.add(AccessToken(session_id=session.id, token_hash=hashlib.sha256(b"qa-access").hexdigest(), expires_at=now() + timedelta(minutes=15)))
            db.add(RefreshToken(session_id=session.id, token_hash=hashlib.sha256(b"qa-refresh").hexdigest()))
            db.add(PasswordResetToken(user_id=user.id, user_version=user.version, token_hash=hashlib.sha256(b"qa-reset").hexdigest(), expires_at=now() + timedelta(minutes=15)))
            db.add(Lead(customer="Backup QA", division="MMC", description="Embedded firmware", assignee_user_id=user.id))
            db.add(Customer(name="Backup QA", divisions=["MMC"], contacts=[{"phone": "1234567890"}], assignee_user_id=user.id))
            document = snapshot(QuotationDocument(number="BACKUP-QA-001", customer="Backup QA", division="MMC", date="2026-11-05", validUntil="2026-12-05", items=[{"description": "IoT firmware", "quantity": 1, "rate": 100, "billing": "One-time"}]))
            content = generate_pdf(document)
            quote = Quotation(number="BACKUP-QA-001", number_key="backup-qa-001", division="MMC", customer="Backup QA", source="Created", status="Draft", document=document, assignee_user_id=user.id)
            db.add(quote)
            db.flush()
            db.add(QuotationFile(quotation_id=quote.id, revision=1, name="qa.pdf", size=len(content), sha256=hashlib.sha256(content).hexdigest(), content=content, snapshot=document))
            db.commit()
        def qa_db():
            with factory() as db:
                yield db
        app.dependency_overrides[get_db] = qa_db
        with patch.object(settings, "DATABASE_URL", url.render_as_string(hide_password=False)), patch.object(settings, "BACKUP_RESTORE_ADMIN_URL", type(settings.BACKUP_RESTORE_ADMIN_URL)("")), patch.object(settings, "OPS_DIRECTORY", directory), patch("app.services.request_limits.SessionLocal", factory):
            result = create_backup(verify=True)
            key = load_key(root_path() / "keys" / "backup.key")
            manifest, archive = read_manifest(result["backupId"], key)
            assert manifest["database"]["pdfCount"] == 1
            assert manifest["restoreVerifiedAt"]
            assert archive.read_bytes()[:8] == b"ENGENBK1"
            assert not any((directory / "work").iterdir())
            with TestClient(app, headers={"X-CRM-Request": "1"}) as client:
                assert client.get("/api/ready").status_code == 200
                login = client.post("/api/auth/login", json={"email": "qa-backup@example.test", "password": "QaBackup123"})
                assert login.status_code == 200
                status = client.get("/api/ops/status", headers={"Authorization": "Bearer " + login.json()["accessToken"]})
                assert status.status_code == 200
                assert status.json()["backup"]["status"] == "fresh"
                assert status.json()["backup"]["restoreVerifiedAt"]
                assert "x-request-id" in status.headers
            recovered = restore_check(result["backupId"], keep_new=True)
            recovered_name = recovered["database"]
            assert re.fullmatch(r"engen_recovered_[a-f0-9]{32}", recovered_name)
            recovered_engine = create_engine(source.set(database=recovered_name), connect_args={"connect_timeout": 5})
            try:
                with recovered_engine.connect() as connection:
                    assert connection.scalar(text("SELECT count(*) FROM auth_sessions WHERE revoked_at IS NULL")) == 0
                    assert connection.scalar(text("SELECT count(*) FROM access_tokens")) == 0
                    assert connection.scalar(text("SELECT count(*) FROM refresh_tokens")) == 0
                    assert connection.scalar(text("SELECT count(*) FROM password_reset_tokens WHERE consumed_at IS NULL")) == 0
                    assert connection.scalar(text("SELECT count(*) FROM quotation_files")) == 1
            finally:
                recovered_engine.dispose()
            # Same-length archive corruption must fail before creating/restoring a target.
            damaged = bytearray(archive.read_bytes())
            damaged[len(damaged) // 2] ^= 1
            archive.write_bytes(damaged)
            try:
                restore_check(result["backupId"])
            except ValueError:
                pass
            else:
                raise AssertionError("Tampered archive was accepted")
            assert not any((directory / "work").iterdir())
        print("Disposable PostgreSQL backup/restore passed: table/PDF fingerprints matched; restore-new revoked old sessions/reset links; tampered archive rejected; Owner monitoring/readiness passed.")
    finally:
        app.dependency_overrides.clear()
        if qa_engine:
            qa_engine.dispose()
        if recovered_name:
            assert re.fullmatch(r"engen_recovered_[a-f0-9]{32}", recovered_name) and recovered_name != source.database
            with maintenance.connect() as connection:
                connection.exec_driver_sql('DROP DATABASE "' + recovered_name + '" WITH (FORCE)')
        if created:
            assert re.fullmatch(r"engen_backup_qa_[a-f0-9]{32}", name) and name != source.database
            with maintenance.connect() as connection:
                connection.exec_driver_sql('DROP DATABASE "' + name + '" WITH (FORCE)')
        with maintenance.connect() as connection:
            assert connection.scalar(text("SELECT count(*) FROM pg_database WHERE datname=:name"), {"name": name}) == 0
        maintenance.dispose()
        assert directory.is_relative_to(area.resolve()) and directory.name.startswith("backup-qa-")
        shutil.rmtree(directory)
    print("QA databases, temporary key/archive/logs removed. No real backup or schedule configured; live CRM data unchanged.")


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        print("Backup/monitor integration failed (" + type(error).__name__ + "). No credentials or tool stderr printed.")
        raise SystemExit(1) from None
