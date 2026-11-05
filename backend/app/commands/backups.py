import argparse
import json
from app.services.backups import backup_status, create_backup, restore_check
from app.services.ops_files import root_path, write_json
from datetime import datetime, timezone


def record_job(command, ok, error_type=None):
    try:
        path = root_path() / "state" / "backup-job.json"
        if path.parent.is_dir() and not path.parent.is_symlink() and not path.parent.is_junction():
            write_json(path, {"command": command, "ok": ok, "finishedAt": datetime.now(timezone.utc).isoformat(), "errorType": error_type})
    except (OSError, ValueError):
        pass


def main():
    parser = argparse.ArgumentParser(description="ENGEN encrypted database backup and isolated restore drill")
    commands = parser.add_subparsers(dest="command", required=True)
    create = commands.add_parser("create")
    create.add_argument("--verify", action="store_true", help="Restore into a fresh temporary database and compare the snapshot")
    restore = commands.add_parser("restore-check")
    restore.add_argument("backup_id")
    recover = commands.add_parser("restore-new", help="Keep a verified new database; never overwrite or switch the live database")
    recover.add_argument("backup_id")
    commands.add_parser("status")
    args = parser.parse_args()
    try:
        result = create_backup(args.verify) if args.command == "create" else restore_check(args.backup_id, keep_new=args.command == "restore-new") if args.command in {"restore-check", "restore-new"} else backup_status()
        if args.command != "status":
            record_job(args.command, True)
        print(json.dumps(result, sort_keys=True))
    except Exception as error:
        if args.command != "status":
            record_job(args.command, False, type(error).__name__)
        # Never print database URL, tool stderr, SQL parameters, key or traceback.
        print(json.dumps({"status": "failed", "errorType": type(error).__name__, "message": "Backup operation failed. Check tools, key, storage and restore-role permissions."}))
        raise SystemExit(1) from None


if __name__ == "__main__":
    main()
