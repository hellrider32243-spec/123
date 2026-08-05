#!/usr/bin/env python3
"""Hysteria2 command auth for the relay.

Hysteria invokes:  hy2_check_auth.py <addr> <auth> <tx>
Accept the UUID when it is present in the synced allow-list (pushed by the
main server's sync_ams.py). The file is read fresh on every auth attempt, so
updating it takes effect immediately with no restart. On success: print the
uuid to stdout and exit 0.
"""
from __future__ import annotations

import os
import re
import sys

ALLOW_FILE = os.environ.get("HY2_ALLOW_FILE", "/etc/hysteria/allowed_uuids.txt")
UUID_RE = re.compile(
    r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"
)


def normalize_auth(raw: str) -> str:
    auth = (raw or "").strip()
    if ":" in auth:
        user, password = auth.split(":", 1)
        if user != password:  # userpass form uuid:uuid
            return ""
        auth = user
    return auth.strip()


def main() -> int:
    if len(sys.argv) >= 3:
        auth_raw = sys.argv[2]
    elif len(sys.argv) == 2:
        auth_raw = sys.argv[1]
    else:
        return 1
    uuid = normalize_auth(auth_raw)
    if not UUID_RE.match(uuid):
        return 1
    try:
        with open(ALLOW_FILE, encoding="utf-8", errors="ignore") as fh:
            allowed = {line.strip() for line in fh if line.strip()}
    except OSError:
        return 1
    if uuid in allowed:
        sys.stdout.write(uuid)
        sys.stdout.flush()
        return 0
    return 1


if __name__ == "__main__":
    sys.exit(main())
