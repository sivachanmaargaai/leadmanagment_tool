"""Private local operations storage; no files from here are served by HTTP."""
import csv
import json
import os
from pathlib import Path
import re
import subprocess
from uuid import uuid4
from app.core.config import settings


def root_path():
    path = settings.OPS_DIRECTORY.expanduser().absolute()
    backend = Path(__file__).resolve().parents[2]
    if (
        path.is_symlink()
        or getattr(path, "is_junction", lambda: False)()
        or path == Path(path.anchor)
        or path == backend
        or path in backend.parents
    ):
        raise ValueError("Choose a dedicated operations directory")
    return path.resolve()


def secure_directory(path):
    path = Path(path)
    if path.is_symlink() or getattr(path, "is_junction", lambda: False)():
        raise ValueError("Operations directories cannot be links or junctions")
    path.mkdir(parents=True, exist_ok=True, mode=0o700)
    if os.name == "nt":
        user = subprocess.run(["whoami", "/user", "/fo", "csv", "/nh"], capture_output=True, text=True, timeout=10, check=True)
        sid = next(csv.reader(user.stdout.strip().splitlines()))[1]
        if not re.fullmatch(r"S-1-\d+(?:-\d+)+", sid):
            raise ValueError("Could not resolve operations owner")
        result = subprocess.run(["icacls", str(path), "/inheritance:r", "/grant:r", f"*{sid}:(OI)(CI)F"], capture_output=True, timeout=10)
        if result.returncode:
            raise OSError("Could not restrict operations directory access")
    else:
        path.chmod(0o700)
    return path


def prepare_paths():
    root = secure_directory(root_path())
    return {name: secure_directory(root / name) for name in ("backups", "keys", "work", "state")}


def write_json(path, data):
    path = Path(path)
    temporary = path.with_name(path.name + "." + uuid4().hex + ".partial")
    try:
        with temporary.open("x", encoding="utf-8") as stream:
            json.dump(data, stream, sort_keys=True, separators=(",", ":"))
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)
