"""Lookup a NL Reality vless for a Telegram user from 4VPS x-ui (no Frankfurt)."""
from __future__ import annotations

import os
import re
import sqlite3
import urllib.parse
from datetime import datetime, timezone
from typing import Any, Optional

XUI_DB = os.getenv("XUI_DB_PATH", "/etc/x-ui/x-ui.db")
AMS_HOST = os.getenv("AMS_HOST", os.getenv("PUBLIC_VLESS_HOST", "139.28.240.160"))
AMS_PORT = int(os.getenv("AMS_PORT", os.getenv("PUBLIC_VLESS_PORT", "443")) or "443")
AMS_SNI = os.getenv("AMS_SNI", os.getenv("SNI", "deepl.com"))
AMS_PBK = os.getenv("AMS_PBK", os.getenv("REALITY_PBK", "-IYnX45q6qyRMrl_bTLLeW97TCBdZW0aTNu7WBF4Nm0"))
AMS_SID = os.getenv("AMS_SID", os.getenv("REALITY_SID", "a7c31e04"))
AMS_FP = os.getenv("AMS_FP", os.getenv("REALITY_FP", "safari"))
AMS_FLOW = os.getenv("AMS_FLOW", os.getenv("VLESS_FLOW", "xtls-rprx-vision"))
_TG_EMAIL = re.compile(r"^(\d{5,15})_")


def make_nl_tcp_vless(uuid: str, email: str) -> str:
    qemail = urllib.parse.quote(email or uuid, safe="")
    return (
        f"vless://{uuid}@{AMS_HOST}:{AMS_PORT}"
        f"?type=tcp&security=reality"
        f"&sni={urllib.parse.quote(AMS_SNI, safe='')}"
        f"&fp={urllib.parse.quote(AMS_FP, safe='')}"
        f"&pbk={urllib.parse.quote(AMS_PBK, safe='')}"
        f"&sid={urllib.parse.quote(AMS_SID, safe='')}"
        f"&spx=%2F&encryption=none"
        f"&flow={urllib.parse.quote(AMS_FLOW, safe='')}"
        f"#{qemail}"
    )


def _expiry_iso(expiry_time_ms: int) -> Optional[str]:
    if not expiry_time_ms:
        return None
    try:
        return datetime.fromtimestamp(expiry_time_ms / 1000, timezone.utc).isoformat()
    except Exception:
        return None


def lookup_nl_client(user_id: int, xui_db: str = XUI_DB) -> Optional[dict[str, Any]]:
    """Return enabled x-ui client whose email is `{telegram_id}_…`."""
    if user_id <= 0:
        return None
    try:
        conn = sqlite3.connect(f"file:{xui_db}?mode=ro", uri=True)
    except Exception:
        try:
            conn = sqlite3.connect(xui_db)
        except Exception:
            return None
    conn.row_factory = sqlite3.Row
    try:
        rows = list(
            conn.execute(
                "SELECT id, email, uuid, enable, expiry_time FROM clients "
                "WHERE enable = 1 AND email LIKE ? ORDER BY id DESC",
                (f"{int(user_id)}_%",),
            )
        )
    except Exception:
        conn.close()
        return None
    conn.close()
    if not rows:
        return None
    row = rows[0]
    email = str(row["email"] or "")
    m = _TG_EMAIL.match(email)
    if not m or int(m.group(1)) != int(user_id):
        return None
    uuid = str(row["uuid"] or "").strip()
    if not uuid:
        return None
    exp_ms = int(row["expiry_time"] or 0)
    return {
        "email": email,
        "uuid": uuid,
        "vless": make_nl_tcp_vless(uuid, email),
        "expires_at": _expiry_iso(exp_ms),
        "expiry_time": exp_ms,
    }
