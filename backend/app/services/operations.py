from pathlib import Path
import json
import shutil
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.pool import NullPool
from app.core.config import settings
from app.core.observability import metrics
from app.services.backups import backup_status
from app.services.ops_files import root_path


def probe_database():
    engine = None
    reachable = False
    try:
        url = make_url(settings.DATABASE_URL)
        engine = create_engine(url, poolclass=NullPool, connect_args={"connect_timeout": 3} if url.get_backend_name() == "postgresql" else {})
        with engine.connect() as connection:
            if url.get_backend_name() == "postgresql":
                connection.execute(text("SET LOCAL statement_timeout = '2s'"))
            connection.execute(text("SELECT 1"))
            reachable = True
            revision = connection.scalar(text("SELECT version_num FROM alembic_version"))
        config = Config()
        config.set_main_option("script_location", str(Path(__file__).resolve().parents[2] / "migrations"))
        head = ScriptDirectory.from_config(config).get_current_head()
        return {"reachable": True, "schemaCurrent": revision == head}
    except Exception:
        return {"reachable": reachable, "schemaCurrent": False}
    finally:
        if engine is not None:
            engine.dispose()


def operations_status():
    database, backup, snapshot = probe_database(), backup_status(), metrics.snapshot()
    issues = []
    if not database["reachable"] or not database["schemaCurrent"]:
        issues.append("database-not-ready")
    if backup["status"] != "fresh":
        issues.append("backup-" + backup["status"])
    if not backup.get("restoreVerifiedAt"):
        issues.append("restore-drill-not-verified")
    if snapshot["recentServerErrors"] >= settings.OPS_RECENT_ERROR_THRESHOLD:
        issues.append("recent-server-errors")
    storage = {"freeBytes": None, "low": False}
    job = None
    try:
        root = root_path()
        usage = shutil.disk_usage(root if root.exists() else root.parent)
        storage = {"freeBytes": usage.free, "low": usage.free < settings.OPS_MIN_FREE_BYTES}
        if storage["low"]:
            issues.append("low-backup-storage")
        path = root / "state" / "backup-job.json"
        if path.is_file() and not path.is_symlink() and path.stat().st_size <= 4096:
            job = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(job, dict) and job.get("ok") is False:
                issues.append("last-backup-job-failed")
            # Whitelist public fields; never expose arbitrary file contents.
            job = {"ok": job.get("ok") is True, "finishedAt": job.get("finishedAt")} if isinstance(job, dict) else None
    except (OSError, ValueError):
        issues.append("operations-storage-unavailable")
    return {"status": "critical" if "database-not-ready" in issues else "warning" if issues else "ok",
            "issues": issues, "database": database, "backup": backup, "metrics": snapshot,
            "storage": storage, "lastBackupJob": job,
            "automation": "not-configured", "offsiteCopy": "not-configured"}
