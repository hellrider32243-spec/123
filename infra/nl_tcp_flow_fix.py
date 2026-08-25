#!/usr/bin/env python3
"""На 4VPS: TCP Reality inbound требует xtls-rprx-vision per-inbound.

bulkCreate ставит один flow на все инбаунды, поэтому vision пишем
в client_inbounds.flow_override только для inbound_id=2.
"""
from __future__ import annotations

import sqlite3
import subprocess
import sys

DB = "/etc/x-ui/x-ui.db"
TCP_INBOUND_ID = 2
FLOW = "xtls-rprx-vision"


def main() -> int:
    db = sqlite3.connect(DB)
    n = db.execute(
        "UPDATE client_inbounds SET flow_override=? WHERE inbound_id=? AND (flow_override IS NULL OR flow_override='')",
        (FLOW, TCP_INBOUND_ID),
    ).rowcount
    db.commit()
    db.close()
    print(f"tcp flow_override patched={n}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
