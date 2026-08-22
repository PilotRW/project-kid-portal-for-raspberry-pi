#!/usr/bin/env python3
import hashlib
import json
import os
import stat
import sys
import tempfile
from pathlib import Path


DEFAULT_CONFIG_PATH = Path("/etc/kid-portal/config.json")


def usage() -> None:
    print("Usage: kid-portal-reset-parent-pin NEW_PIN [CONFIG_PATH]", file=sys.stderr)


def validate_pin(pin: str) -> None:
    if not pin.isdigit() or len(pin) < 4 or len(pin) > 12:
        print("Parent PIN must be 4-12 digits.", file=sys.stderr)
        sys.exit(2)


def pin_hash(pin: str) -> str:
    return hashlib.sha256(pin.encode("utf-8")).hexdigest()


def atomic_write_json(path: Path, data: dict) -> None:
    existing_stat = path.stat()
    existing_mode = stat.S_IMODE(existing_stat.st_mode)
    fd, tmp_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=str(path.parent), text=True)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(data, handle, indent=2, sort_keys=True)
            handle.write("\n")
        os.chmod(tmp_name, existing_mode)
        try:
            os.chown(tmp_name, existing_stat.st_uid, existing_stat.st_gid)
        except PermissionError:
            pass
        os.replace(tmp_name, path)
    finally:
        if os.path.exists(tmp_name):
            os.unlink(tmp_name)


def main() -> int:
    if len(sys.argv) not in {2, 3}:
        usage()
        return 2

    new_pin = sys.argv[1].strip()
    validate_pin(new_pin)

    config_path = Path(sys.argv[2]) if len(sys.argv) == 3 else Path(os.environ.get("KID_PORTAL_CONFIG", DEFAULT_CONFIG_PATH))
    if not config_path.exists():
        print(f"Config file does not exist: {config_path}", file=sys.stderr)
        return 2

    data = json.loads(config_path.read_text(encoding="utf-8"))
    parent = data.setdefault("parent", {})
    new_hash = pin_hash(new_pin)
    if parent.get("view_pin_sha256") == new_hash:
        print("Parent PIN must be different from viewing PIN.", file=sys.stderr)
        return 2

    parent["pin_sha256"] = new_hash
    atomic_write_json(config_path, data)
    print(f"Parent/admin PIN reset in {config_path}.")
    print("Restart is not required; the next admin request will use the new PIN.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
