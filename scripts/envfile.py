"""Tiny .env editor used by the make targets: `python scripts/envfile.py set KEY VALUE`."""

import sys
from pathlib import Path

ENV = Path(__file__).resolve().parent.parent / ".env"


def set_value(key: str, value: str) -> None:
    lines = ENV.read_text().splitlines() if ENV.exists() else []
    out, done = [], False
    for line in lines:
        if line.split("=", 1)[0].strip() == key:
            out.append(f"{key}={value}")
            done = True
        else:
            out.append(line)
    if not done:
        out.append(f"{key}={value}")
    ENV.write_text("\n".join(out) + "\n")


def get_value(key: str, default: str = "") -> str:
    if not ENV.exists():
        return default
    for line in ENV.read_text().splitlines():
        k, _, v = line.partition("=")
        if k.strip() == key:
            return v.strip()
    return default


if __name__ == "__main__":
    cmd, key, *rest = sys.argv[1:]
    if cmd == "set":
        set_value(key, rest[0])
    elif cmd == "get":
        print(get_value(key, rest[0] if rest else ""))
