import base64
import hashlib
import hmac
import json
import os
from pathlib import Path
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

MAGIC = b"ENGENBK1"
CHUNK = 1024 * 1024


def load_key(path, create=False):
    path = Path(path)
    if path.is_symlink():
        raise ValueError("Backup key cannot be a link")
    if create and not path.exists():
        with os.fdopen(os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), "wb") as stream:
            stream.write(base64.b64encode(os.urandom(32)))
            stream.flush()
            os.fsync(stream.fileno())
    if path.stat().st_size > 128:
        raise ValueError("Invalid backup encryption key")
    key = base64.b64decode(path.read_bytes().strip(), validate=True)
    if len(key) != 32:
        raise ValueError("Invalid backup encryption key")
    return key


def derive(key, purpose):
    return hmac.new(key, purpose, hashlib.sha256).digest()


def sign_manifest(manifest, key):
    payload = {name: value for name, value in manifest.items() if name != "signature"}
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    return hmac.new(derive(key, b"ENGEN metadata v1"), encoded, hashlib.sha256).hexdigest()


def sha256_file(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        while chunk := stream.read(CHUNK):
            digest.update(chunk)
    return digest.hexdigest()


def encrypt_file(source, target, key):
    nonce = os.urandom(12)
    header = MAGIC + nonce
    encryptor = Cipher(algorithms.AES(derive(key, b"ENGEN archive v1")), modes.GCM(nonce)).encryptor()
    encryptor.authenticate_additional_data(header)
    with Path(source).open("rb") as incoming, Path(target).open("xb") as outgoing:
        outgoing.write(header)
        while chunk := incoming.read(CHUNK):
            outgoing.write(encryptor.update(chunk))
        outgoing.write(encryptor.finalize())
        outgoing.write(encryptor.tag)
        outgoing.flush()
        os.fsync(outgoing.fileno())


def decrypt_file(source, target, key):
    source, target = Path(source), Path(target)
    created = False
    try:
        with source.open("rb") as incoming:
            if source.stat().st_size < len(MAGIC) + 12 + 16:
                raise ValueError("Invalid encrypted archive")
            header = incoming.read(len(MAGIC) + 12)
            if not header.startswith(MAGIC):
                raise ValueError("Invalid encrypted archive format")
            incoming.seek(-16, os.SEEK_END)
            tag = incoming.read(16)
            remaining = incoming.tell() - len(header) - 16
            incoming.seek(len(header))
            decryptor = Cipher(algorithms.AES(derive(key, b"ENGEN archive v1")), modes.GCM(header[len(MAGIC):], tag)).decryptor()
            decryptor.authenticate_additional_data(header)
            with target.open("xb") as outgoing:
                created = True
                while remaining:
                    chunk = incoming.read(min(CHUNK, remaining))
                    if not chunk:
                        raise ValueError("Incomplete encrypted archive")
                    outgoing.write(decryptor.update(chunk))
                    remaining -= len(chunk)
                outgoing.write(decryptor.finalize())
                outgoing.flush()
                os.fsync(outgoing.fileno())
    except Exception:
        if created:
            target.unlink(missing_ok=True)
        raise
