"""Encrypted PostgreSQL custom archives; restore drills always use a new database."""
from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import hmac
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
from uuid import uuid4

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import make_url
from sqlalchemy.pool import NullPool
from app.core.config import settings
from app.services.backup_crypto import decrypt_file, encrypt_file, load_key, sha256_file, sign_manifest
from app.services.ops_files import prepare_paths, root_path, write_json

ID_PATTERN = r"engen_\d{8}T\d{6}Z_[a-f0-9]{12}"


def utc_now():
    return datetime.now(timezone.utc)


def pg_url(value):
    url = make_url(value)
    if url.get_backend_name() != "postgresql" or not url.database or not url.username:
        raise ValueError("Backup tools require a PostgreSQL URL with a database and username")
    return url


def db_engine(url, autocommit=False):
    return create_engine(url, poolclass=NullPool, connect_args={"connect_timeout": 5},
                         **({"isolation_level": "AUTOCOMMIT"} if autocommit else {}))


def pg_tools():
    candidates = [Path(settings.PG_BIN_DIRECTORY)] if settings.PG_BIN_DIRECTORY else []
    found = shutil.which("pg_dump")
    if found:
        candidates.append(Path(found).parent)
    if os.name == "nt":
        base = Path(os.environ.get("ProgramFiles", "C:/Program Files")) / "PostgreSQL"
        candidates.extend(sorted(base.glob("*/bin"), key=lambda path: tuple(int(value) for value in re.findall(r"\d+", path.parent.name)), reverse=True))
    suffix = ".exe" if os.name == "nt" else ""
    for directory in candidates:
        dump, restore = directory / ("pg_dump" + suffix), directory / ("pg_restore" + suffix)
        if dump.is_file() and restore.is_file():
            return dump.resolve(), restore.resolve()
    raise ValueError("Set PG_BIN_DIRECTORY to the PostgreSQL client tools directory")


@contextmanager
def job_lock(paths):
    stream = (paths["state"] / "backup.lock").open("a+b")
    try:
        if stream.tell() == 0:
            stream.write(b"0")
            stream.flush()
        stream.seek(0)
        try:
            if os.name == "nt":
                import msvcrt
                msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            raise RuntimeError("Another backup or restore job is running") from None
        try:
            yield
        finally:
            stream.seek(0)
            if os.name == "nt":
                msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(stream.fileno(), fcntl.LOCK_UN)
    finally:
        stream.close()


@contextmanager
def pg_environment(url, directory):
    allowed = {"sslmode": "PGSSLMODE", "sslrootcert": "PGSSLROOTCERT", "sslcert": "PGSSLCERT", "sslkey": "PGSSLKEY", "channel_binding": "PGCHANNELBINDING", "application_name": "PGAPPNAME"}
    if set(url.query) - set(allowed):
        raise ValueError("Unsupported PostgreSQL URL option for backup tools")
    def escape(value):
        value = str(value)
        if "\n" in value or "\r" in value:
            raise ValueError("Invalid PostgreSQL connection field")
        return value.replace("\\", "\\\\").replace(":", "\\:")
    password_file = Path(directory) / "pgpass"
    try:
        with os.fdopen(os.open(password_file, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), "w", encoding="utf-8") as stream:
            stream.write(":".join(escape(value) for value in [url.host or "localhost", url.port or 5432, "*", url.username, url.password or ""]) + "\n")
        env = {key: value for key, value in os.environ.items() if not key.startswith("PG")}
        env.update(PGHOST=url.host or "localhost", PGPORT=str(url.port or 5432), PGUSER=url.username,
                   PGDATABASE=url.database, PGPASSFILE=str(password_file), PGCONNECT_TIMEOUT="5", PGAPPNAME="engen-backup")
        env.update({allowed[key]: str(value) for key, value in url.query.items()})
        yield env
    finally:
        password_file.unlink(missing_ok=True)


def run_tool(arguments, env):
    # Never surface PostgreSQL stderr: it may contain connection/provider details.
    result = subprocess.run([str(value) for value in arguments], env=env, stdout=subprocess.DEVNULL,
                            stderr=subprocess.PIPE, timeout=settings.BACKUP_TOOL_TIMEOUT_SECONDS)
    if result.returncode:
        raise RuntimeError("PostgreSQL backup/restore tool failed; check client version and database permissions")


def fingerprint(connection):
    connection.execute(text("SET LOCAL TIME ZONE 'UTC'"))
    tables = {}
    preparer = connection.dialect.identifier_preparer
    for name in sorted(inspect(connection).get_table_names(schema="public")):
        quoted = preparer.quote_identifier(name)
        digest = hashlib.sha256()
        count = 0
        # Server-side row digests keep PDF/customer/password content out of Python metadata.
        rows = connection.execution_options(stream_results=True).execute(text(
            f"SELECT encode(sha256(convert_to(to_jsonb(t)::text, 'UTF8')), 'hex') AS digest FROM public.{quoted} t ORDER BY digest"))
        for row in rows:
            digest.update(row[0].encode())
            count += 1
        tables[name] = {"rows": count, "fingerprint": digest.hexdigest()}
    pdf = connection.execute(text("SELECT count(*), coalesce(sum(octet_length(content)),0), count(*) FILTER (WHERE sha256 <> encode(sha256(content),'hex') OR size <> octet_length(content)) FROM public.quotation_files")).one()
    if pdf[2]:
        raise ValueError("Stored PDF integrity verification failed")
    revision = connection.scalar(text("SELECT version_num FROM public.alembic_version"))
    return {"tables": tables, "pdfCount": pdf[0], "pdfBytes": int(pdf[1]), "revision": revision}


def manifest_path(backup_id):
    if not re.fullmatch(ID_PATTERN, backup_id):
        raise ValueError("Invalid backup identifier")
    path = root_path() / "backups" / (backup_id + ".json")
    if path.is_symlink() or path.parent.is_symlink() or path.parent.is_junction():
        raise ValueError("Backup paths cannot be links")
    return path


def read_manifest(backup_id, key):
    path = manifest_path(backup_id)
    if path.stat().st_size > 262144:
        raise ValueError("Invalid backup manifest")
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or data.get("id") != backup_id or data.get("format") != "engen-backup-v1" or not hmac.compare_digest(str(data.get("signature", "")), sign_manifest(data, key)):
        raise ValueError("Backup manifest authentication failed")
    if data.get("archive") != backup_id + ".dump.enc":
        raise ValueError("Invalid backup archive path")
    archive = path.parent / data["archive"]
    if archive.is_symlink() or not archive.is_file() or archive.stat().st_size != data["bytes"]:
        raise ValueError("Backup archive is missing or changed")
    return data, archive


def save_manifest(data, key):
    data["signature"] = sign_manifest(data, key)
    write_json(manifest_path(data["id"]), data)


def backup_status():
    """Read-only status; never creates a key or configures a schedule."""
    try:
        key = load_key(root_path() / "keys" / "backup.key")
        candidates = sorted((root_path() / "backups").glob("engen_*.json"), reverse=True)
        for path in candidates:
            try:
                data, _ = read_manifest(path.stem, key)
                at = datetime.fromisoformat(data["createdAt"])
                if at.tzinfo is None:
                    raise ValueError("Invalid backup timestamp")
                age = (utc_now() - at).total_seconds() / 3600
                return {"status": "fresh" if -0.1 <= age <= settings.BACKUP_MAX_AGE_HOURS else "stale",
                        "createdAt": data["createdAt"], "ageHours": round(max(0, age), 2),
                        "restoreVerifiedAt": data.get("restoreVerifiedAt"), "backupId": data["id"]}
            except (ValueError, OSError, KeyError, TypeError):
                continue
        return {"status": "missing-or-invalid", "restoreVerifiedAt": None}
    except (ValueError, OSError):
        return {"status": "not-configured", "restoreVerifiedAt": None}


def prune_backups(key):
    valid = []
    for path in (root_path() / "backups").glob("engen_*.json"):
        try:
            data, archive = read_manifest(path.stem, key)
            valid.append((data, archive, path))
        except (ValueError, OSError, KeyError, TypeError):
            continue
    valid.sort(key=lambda item: item[0]["createdAt"], reverse=True)
    keep = {item[0]["id"] for item in valid[:settings.BACKUP_RETENTION_COUNT]}
    verified = next((item[0]["id"] for item in valid if item[0].get("restoreVerifiedAt")), None)
    keep.add(verified)
    for data, archive, path in valid:
        if data["id"] not in keep:
            # Both names came from a signed, validated manifest under the backup directory.
            archive.unlink()
            path.unlink()


def create_backup(verify=False):
    paths = prepare_paths()
    with job_lock(paths):
        key_path = paths["keys"] / "backup.key"
        if not key_path.exists() and any(paths["backups"].glob("*.enc")):
            raise ValueError("Encryption key is missing; restore the saved key before creating another backup")
        key = load_key(key_path, create=True)
        backup_id = "engen_" + utc_now().strftime("%Y%m%dT%H%M%SZ_") + uuid4().hex[:12]
        dump_tool, _ = pg_tools()
        url = pg_url(settings.DATABASE_URL)
        engine = db_engine(url)
        try:
            with tempfile.TemporaryDirectory(dir=paths["work"]) as temporary:
                dump = Path(temporary) / "snapshot.dump"
                with engine.connect().execution_options(isolation_level="REPEATABLE READ") as connection:
                    connection.execute(text("SET TRANSACTION READ ONLY"))
                    snapshot = connection.scalar(text("SELECT pg_export_snapshot()"))
                    metadata = fingerprint(connection)
                    with pg_environment(url, temporary) as env:
                        run_tool([dump_tool, "--no-password", "--format=custom", "--no-owner", "--no-privileges", "--snapshot=" + snapshot, "--file=" + str(dump)], env)
                archive = paths["backups"] / (backup_id + ".dump.enc")
                pending = archive.with_name(archive.name + ".partial")
                try:
                    encrypt_file(dump, pending, key)
                    os.replace(pending, archive)
                finally:
                    pending.unlink(missing_ok=True)
                data = {"format": "engen-backup-v1", "id": backup_id, "createdAt": utc_now().isoformat(),
                        "archive": archive.name, "bytes": archive.stat().st_size, "sha256": sha256_file(archive),
                        "database": metadata, "restoreVerifiedAt": None}
                save_manifest(data, key)
            if verify:
                restore_check(backup_id, paths=paths, key=key)
            prune_backups(key)
            return {"backupId": backup_id, "encryptedBytes": data["bytes"], "verified": verify}
        finally:
            engine.dispose()


def restore_check(backup_id, paths=None, key=None, keep_new=False):
    """A drill only: never writes to an existing or configured source database."""
    if paths is None:
        paths = prepare_paths()
        with job_lock(paths):
            return restore_check(backup_id, paths, load_key(paths["keys"] / "backup.key"), keep_new=keep_new)
    data, archive = read_manifest(backup_id, key)
    if not hmac.compare_digest(sha256_file(archive), data["sha256"]):
        raise ValueError("Encrypted backup checksum failed")
    source = pg_url(settings.DATABASE_URL)
    admin = pg_url(settings.BACKUP_RESTORE_ADMIN_URL.get_secret_value() or settings.DATABASE_URL)
    name = ("engen_recovered_" if keep_new else "engen_restore_check_") + uuid4().hex
    if not re.fullmatch(r"engen_(?:restore_check|recovered)_[a-f0-9]{32}", name) or name in {source.database, admin.database}:
        raise ValueError("Unsafe restore test database name")
    maintenance = db_engine(admin.set(database="postgres"), autocommit=True)
    restored = None
    created = False
    retain = False
    _, restore_tool = pg_tools()
    try:
        with tempfile.TemporaryDirectory(dir=paths["work"]) as temporary:
            dump = Path(temporary) / "restore.dump"
            decrypt_file(archive, dump, key)  # Authentication must finish before pg_restore sees plaintext.
            with maintenance.connect() as connection:
                connection.exec_driver_sql('CREATE DATABASE "' + name + '" TEMPLATE template0')
                created = True
            target = admin.set(database=name)
            with pg_environment(target, temporary) as env:
                run_tool([restore_tool, "--no-password", "--exit-on-error", "--single-transaction", "--no-owner", "--no-privileges", "--dbname=" + name, str(dump)], env)
            restored = db_engine(target)
            with restored.connect().execution_options(isolation_level="REPEATABLE READ") as connection:
                connection.execute(text("SET TRANSACTION READ ONLY"))
                actual = fingerprint(connection)
            if actual != data["database"]:
                raise ValueError("Restore verification did not match the source snapshot")
            if keep_new:
                # Recovery never revives old sessions or password-reset links.
                with restored.begin() as connection:
                    connection.execute(text("UPDATE public.auth_sessions SET revoked_at=now() WHERE revoked_at IS NULL"))
                    connection.execute(text("UPDATE public.password_reset_tokens SET consumed_at=now() WHERE consumed_at IS NULL"))
                    connection.execute(text("DELETE FROM public.access_tokens"))
                    connection.execute(text("DELETE FROM public.refresh_tokens"))
            data["restoreVerifiedAt"] = utc_now().isoformat()
            save_manifest(data, key)
            retain = keep_new
            return {"backupId": backup_id, "verified": True, "tables": len(actual["tables"]), "pdfCount": actual["pdfCount"],
                    **({"database": name, "sessionsRevoked": True, "liveConfigurationChanged": False} if keep_new else {})}
    finally:
        if restored:
            restored.dispose()
        if created and not retain:
            # Exact internally generated database, created by this invocation; never a supplied target.
            with maintenance.connect() as connection:
                connection.exec_driver_sql('DROP DATABASE "' + name + '" WITH (FORCE)')
        maintenance.dispose()
