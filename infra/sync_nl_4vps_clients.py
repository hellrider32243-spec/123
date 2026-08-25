#!/usr/bin/env python3
"""Зеркало активных ключей bot.db → x-ui 4VPS (TCP/gRPC/Hysteria).

Новые выдачи после переезда NL иначе получают JSON на 139.28.240.160,
но UUID нет в панели — Happ «не подключается».

  cd /opt/nordwings/app
  ./venv/bin/python sync_nl_4vps_clients.py
"""
from __future__ import annotations

import json
import os
import re
import sqlite3
import time
import urllib.error
import urllib.request
import http.cookiejar
from pathlib import Path

BOT_DB = os.getenv("DB_PATH", "/opt/3xui-bot/bot.db")
_ENV_FILE = Path(os.getenv("NL_XUI_ENV_FILE", "/opt/nordwings/app/.nl-xui.env"))


def _load_env_file() -> None:
    if not _ENV_FILE.exists():
        return
    for raw in _ENV_FILE.read_text().splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip())


_load_env_file()

NL_XUI_URL = os.getenv("NL_XUI_URL", "http://139.28.240.160:2053").rstrip("/")
NL_XUI_USER = os.getenv("NL_XUI_USER", "triton")
NL_XUI_PASSWORD = os.getenv("NL_XUI_PASSWORD", "")
NL_INBOUND_IDS = [int(x) for x in os.getenv("NL_XUI_INBOUND_IDS", "1,2,3").split(",") if x.strip()]
TCP_INBOUND_ID = int(os.getenv("NL_TCP_INBOUND_ID", "2"))
TCP_FLOW = os.getenv("TCP_VLESS_FLOW", "xtls-rprx-vision")


def sanitize_email(email: str, uuid: str) -> str:
    s = "".join(ch if ch.isascii() and (ch.isalnum() or ch in "._-") else "_" for ch in (email or ""))
    s = re.sub(r"_+", "_", s).strip("._-")
    for suffix in ("_tcp", "_xhttp"):
        if s.endswith(suffix):
            s = s[: -len(suffix)].rstrip("_")
    if not s:
        s = "u_" + uuid.split("-")[0]
    return s[:60]


def uuid_from_vless(link: str) -> str:
    m = re.search(r"vless://([^@/]+)", link or "")
    return (m.group(1) if m else "").strip()


def active_keys(db_path: str) -> list[dict]:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        """
        SELECT user_id, email, vless_link
        FROM keys
        WHERE is_active = 1
          AND vless_link IS NOT NULL
          AND vless_link != ''
        """
    ).fetchall()
    conn.close()
    out = []
    seen = set()
    for r in rows:
        uid = uuid_from_vless(r["vless_link"])
        if not uid or uid in seen:
            continue
        seen.add(uid)
        out.append(
            {
                "user_id": r["user_id"],
                "uuid": uid,
                "email": sanitize_email(r["email"] or "", uid),
            }
        )
    return out


class NlPanel:
    def __init__(self) -> None:
        self.base = NL_XUI_URL
        self.api = self.base + "/panel/panel/api"
        self.csrf = ""
        self.cj = http.cookiejar.CookieJar()
        self.opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(self.cj))

    def _csrf_from(self, html: str) -> str:
        m = re.search(r'name="csrf-token" content="([^"]+)"', html)
        return m.group(1) if m else ""

    def call(self, method: str, path: str, body=None, timeout: int = 120):
        headers = {
            "Accept": "application/json",
            "X-CSRF-Token": self.csrf,
            "X-Requested-With": "XMLHttpRequest",
        }
        data = None
        if body is not None:
            headers["Content-Type"] = "application/json"
            data = json.dumps(body, ensure_ascii=False).encode()
        req = urllib.request.Request(self.api + path, data=data, headers=headers, method=method)
        try:
            with self.opener.open(req, timeout=timeout) as resp:
                raw = resp.read()
                try:
                    return resp.status, json.loads(raw.decode() or "null")
                except json.JSONDecodeError:
                    return resp.status, raw.decode()[:500]
        except urllib.error.HTTPError as e:
            raw = e.read()
            try:
                parsed = json.loads(raw.decode() or "null")
            except Exception:
                parsed = raw.decode()[:500]
            return e.code, parsed

    def login(self) -> None:
        html = self.opener.open(self.base + "/panel/", timeout=15).read().decode()
        self.csrf = self._csrf_from(html)
        req = urllib.request.Request(
            self.base + "/panel/login",
            data=json.dumps({"username": NL_XUI_USER, "password": NL_XUI_PASSWORD}).encode(),
            headers={
                "Content-Type": "application/json",
                "X-CSRF-Token": self.csrf,
                "X-Requested-With": "XMLHttpRequest",
            },
            method="POST",
        )
        with self.opener.open(req, timeout=15) as resp:
            out = json.loads(resp.read().decode())
            if not out.get("success"):
                raise SystemExit(f"NL x-ui login failed: {out}")
        html2 = self.opener.open(self.base + "/panel/panel/", timeout=15).read().decode()
        self.csrf = self._csrf_from(html2) or self.csrf


def existing_uuids() -> set[str]:
    """Список UUID через API list, без SSH на sqlite."""
    return set()


def main() -> int:
    if not NL_XUI_PASSWORD:
        print("NL_XUI_PASSWORD empty", flush=True)
        return 2
    keys = active_keys(BOT_DB)
    panel = NlPanel()
    panel.login()
    code, listed = panel.call("GET", "/inbounds/list")
    if code != 200 or not (listed or {}).get("success"):
        print("inbounds/list failed", code, listed)
        return 1
    have: set[str] = set()
    emails: set[str] = set()
    for ib in listed.get("obj") or []:
        for st in ib.get("clientStats") or []:
            u = (st.get("uuid") or "").strip()
            if u:
                have.add(u)
            e = (st.get("email") or "").strip().lower()
            if e:
                emails.add(e)
        settings = ib.get("settings") or {}
        if isinstance(settings, str):
            try:
                settings = json.loads(settings)
            except Exception:
                settings = {}
        for cl in settings.get("clients") or []:
            u = (cl.get("id") or cl.get("uuid") or "").strip()
            if u:
                have.add(u)
            e = (cl.get("email") or "").strip().lower()
            if e:
                emails.add(e)

    missing = [k for k in keys if k["uuid"] not in have]
    print(f"active_keys={len(keys)} on_nl={len(have)} missing={len(missing)}", flush=True)
    if not missing:
        return 0

    payloads = []
    used_emails = set(emails)
    for k in missing:
        email = k["email"]
        base = email
        n = 2
        while email.lower() in used_emails:
            email = f"{base}_{n}"[:60]
            n += 1
        used_emails.add(email.lower())
        payloads.append(
            {
                "client": {
                    "id": k["uuid"],
                    "email": email,
                    "enable": True,
                    "limitIp": 3,
                    "totalGB": 0,
                    "expiryTime": 0,
                    "flow": "",
                    "subId": "",
                    "comment": f"uid:{k['user_id']}",
                },
                "inboundIds": NL_INBOUND_IDS,
            }
        )

    created = 0
    skipped = []
    chunk = 20
    for i in range(0, len(payloads), chunk):
        part = payloads[i : i + chunk]
        code, body = panel.call("POST", "/clients/bulkCreate", part, timeout=180)
        obj = (body or {}).get("obj") if isinstance(body, dict) else None
        c = int((obj or {}).get("created") or 0) if isinstance(obj, dict) else 0
        sk = (obj or {}).get("skipped") or [] if isinstance(obj, dict) else []
        created += c
        skipped.extend(sk)
        print(f"bulk {i}-{i+len(part)} created={c} skipped={len(sk)} http={code}", flush=True)
        if sk[:5]:
            print("  skip", sk[:5], flush=True)
        time.sleep(0.05)

    # sqlite flow_override только на самой 4VPS.
    xui_db = Path(os.getenv("NL_XUI_DB", ""))
    local_panel = NL_XUI_URL.startswith("http://127.0.0.1") or NL_XUI_URL.startswith("http://localhost")
    if not xui_db and local_panel:
        xui_db = Path("/etc/x-ui/x-ui.db")
    if xui_db and xui_db.exists() and local_panel:
        import sqlite3 as _sq

        db = _sq.connect(str(xui_db))
        n = db.execute(
            "UPDATE client_inbounds SET flow_override=? WHERE inbound_id=? AND (flow_override IS NULL OR flow_override='')",
            (TCP_FLOW, TCP_INBOUND_ID),
        ).rowcount
        db.commit()
        db.close()
        print(f"tcp flow_override rows={n}", flush=True)
    else:
        ssh_key = os.getenv("NL_XUI_SSH_KEY", "/root/.ssh/nl4vps_sync")
        ssh_host = os.getenv("NL_XUI_SSH_HOST", "139.28.240.160")
        import subprocess

        r = subprocess.run(
            [
                "ssh",
                "-i",
                ssh_key,
                "-o",
                "BatchMode=yes",
                "-o",
                "ConnectTimeout=10",
                f"root@{ssh_host}",
                "python3 /root/nl_tcp_flow_fix.py",
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )
        print((r.stdout or r.stderr or "").strip(), "ssh_rc", r.returncode, flush=True)

    code, body = panel.call("POST", "/server/restartXrayService", {})
    print(f"CREATED extra={created} SKIPPED={len(skipped)} restart={code} {body}", flush=True)
    return 0 if created or not skipped else 1


if __name__ == "__main__":
    raise SystemExit(main())
