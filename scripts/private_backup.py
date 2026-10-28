"""Back up ignored project data with AES-256-GCM; keep the recovery key local."""
import argparse
import io
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import zipfile

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

ROOT = Path(__file__).resolve().parents[1]
HEADER = b"PARKWISE-AESGCM-1\n"
KEY = ROOT / "outputs" / "parkwise-backup-recovery.key"
ARCHIVE = ROOT / "backups" / "parkwise-private.aesgcm"
SKIP = {".git", "node_modules", ".venv", ".venv313", "venv", "env", "__pycache__", ".pytest_cache", "htmlcov"}


def create():
    KEY.parent.mkdir(exist_ok=True)
    if not KEY.exists():
        with KEY.open("xb") as handle:
            handle.write(AESGCM.generate_key(bit_length=256))
    candidates = []
    for folder, directories, files in os.walk(ROOT):
        directories[:] = [d for d in directories if d not in SKIP]
        for name in files:
            path = Path(folder) / name
            if path in {KEY, ARCHIVE} or name == "parkwise-private-restored.zip":
                continue
            candidates.append(path.relative_to(ROOT).as_posix())
    ignored = subprocess.run(["git", "check-ignore", "-z", "--stdin"], input=("\0".join(candidates) + "\0").encode(), capture_output=True, cwd=ROOT)
    if ignored.returncode not in (0, 1):
        raise RuntimeError("Unable to enumerate ignored files")
    paths = [value.decode() for value in ignored.stdout.split(b"\0") if value]
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        for relative in paths:
            path = ROOT / relative
            if path.suffix in {".db", ".sqlite", ".sqlite3"}:
                # Snapshot live SQLite databases through the backup API.
                with sqlite3.connect(path.as_uri() + "?mode=ro", uri=True) as source, sqlite3.connect(":memory:") as target:
                    source.backup(target)
                    archive.writestr(relative, target.serialize())
            else:
                archive.write(path, relative)
        archive.writestr("backup-manifest.json", json.dumps({"files": paths}, indent=2))
    nonce = os.urandom(12)
    encrypted = AESGCM(KEY.read_bytes()).encrypt(nonce, buffer.getvalue(), HEADER)
    # Verify before writing the publishable encrypted archive.
    assert AESGCM(KEY.read_bytes()).decrypt(nonce, encrypted, HEADER) == buffer.getvalue()
    ARCHIVE.parent.mkdir(exist_ok=True)
    ARCHIVE.write_bytes(HEADER + nonce + encrypted)
    print(f"Encrypted backup verified: {len(paths)} local files, {ARCHIVE.stat().st_size} bytes")
    print("Recovery key remains local at outputs/parkwise-backup-recovery.key")


def restore():
    data = ARCHIVE.read_bytes()
    if not data.startswith(HEADER):
        raise ValueError("Unknown archive format")
    nonce = data[len(HEADER):len(HEADER)+12]
    plaintext = AESGCM(KEY.read_bytes()).decrypt(nonce, data[len(HEADER)+12:], HEADER)
    output = ROOT / "outputs" / "parkwise-private-restored.zip"
    output.write_bytes(plaintext)
    print(f"Decrypted ZIP saved to {output}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--restore", action="store_true")
    args = parser.parse_args()
    restore() if args.restore else create()
