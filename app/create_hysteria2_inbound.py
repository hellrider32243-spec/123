#!/usr/bin/env python3
"""
Создать настоящий inbound Hysteria2 (UDP/QUIC) в x-ui.

TLS: Let's Encrypt на wingsvpn.<ip>.sslip.io (HTTP-01 через nginx :80).
Порт по умолчанию — UDP 443 (TCP :443 остаётся Reality).
Auth каждого клиента = его VLESS UUID.

  cd /opt/nordwings/app
  ./venv/bin/python create_hysteria2_inbound.py --dry-run
  ./venv/bin/python create_hysteria2_inbound.py
"""
from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, "/opt/nordwings/app")
os.chdir("/opt/nordwings/app")

from bot_api import xui  # noqa: E402

HY2_PORT = int(os.getenv("AMS_HY2_PORT", os.getenv("HYSTERIA_PORT", "443")))
HY2_SNI = os.getenv("AMS_HY2_SNI", os.getenv("HYSTERIA_SNI", "wingsvpn.139.28.240.160.sslip.io"))
CERT_DIR = Path(os.getenv("AMS_HY2_CERT_DIR", f"/etc/letsencrypt/live/{HY2_SNI}"))
CERT_FILE = os.getenv("AMS_HY2_CERT", str(CERT_DIR / "fullchain.pem"))
KEY_FILE = os.getenv("AMS_HY2_KEY", str(CERT_DIR / "privkey.pem"))
SRC_INBOUND_ID = int(os.getenv("TCP_INBOUND_ID", "2"))
XUI_DB = "/etc/x-ui/x-ui.db"
ENV_PATHS = ("/opt/nordwings/app/.env", "/opt/nordwings-web/.env")


def parse_clients(inbound: dict) -> list:
    raw = inbound.get("settings") or "{}"
    settings = json.loads(raw) if isinstance(raw, str) else raw
    return list(settings.get("clients") or [])


def inbound_by_port_or_remark(port: int) -> dict | None:
    if not xui._ensure_auth():
        return None
    r = xui.session.get(f"{xui.base_url}/panel/api/inbounds/list", timeout=15)
    data = xui._parse_response(r)
    for ib in data.get("obj") or []:
        remark = (ib.get("remark") or "").lower()
        proto = (ib.get("protocol") or "").lower()
        if "hysteria2" in remark or proto in ("hysteria", "hysteria2"):
            return ib
        if int(ib.get("port") or 0) == port and proto in ("hysteria", "hysteria2"):
            return ib
    return None


def build_stream() -> dict:
    return {
        "network": "hysteria",
        "security": "tls",
        "tlsSettings": {
            "serverName": HY2_SNI,
            "alpn": ["h3"],
            "minVersion": "1.3",
            "certificates": [
                {
                    "certificateFile": CERT_FILE,
                    "keyFile": KEY_FILE,
                }
            ],
        },
        "hysteriaSettings": {
            "version": 2,
        },
    }


def create_inbound(dry_run: bool) -> int | None:
    existing = inbound_by_port_or_remark(HY2_PORT)
    if existing:
        print(f"  inbound already exists id={existing.get('id')} port={existing.get('port')} proto={existing.get('protocol')}")
        return int(existing["id"])

    sniffing = {
        "enabled": True,
        "destOverride": ["http", "tls", "quic"],
        "metadataOnly": False,
        "routeOnly": False,
    }
    payload = {
        "up": 0,
        "down": 0,
        "total": 0,
        "remark": "NL Hysteria2",
        "enable": True,
        "expiryTime": 0,
        "listen": "",
        "port": HY2_PORT,
        "protocol": "hysteria2",
        "settings": json.dumps({"version": 2, "clients": []}),
        "streamSettings": json.dumps(build_stream(), ensure_ascii=False),
        "sniffing": json.dumps(sniffing, ensure_ascii=False),
        "allocate": json.dumps({"strategy": "always", "refresh": 5, "concurrency": 3}),
    }
    if dry_run:
        print("DRY create Hysteria2 inbound")
        print(json.dumps({**payload, "streamSettings": json.loads(payload["streamSettings"])}, indent=2)[:2500])
        return None

    r = xui.session.post(f"{xui.base_url}/panel/api/inbounds/add", json=payload, timeout=20)
    data = xui._parse_response(r)
    if not data.get("success"):
        print("hysteria2 protocol failed, retry hysteria:", data.get("msg"))
        payload["protocol"] = "hysteria"
        r = xui.session.post(f"{xui.base_url}/panel/api/inbounds/add", json=payload, timeout=20)
        data = xui._parse_response(r)
    if not data.get("success"):
        print("FAIL add inbound:", data, file=sys.stderr)
        sys.exit(1)
    again = inbound_by_port_or_remark(HY2_PORT)
    if not again:
        print("FAIL: inbound not found after create", data, file=sys.stderr)
        sys.exit(1)
    print(f"  created inbound id={again['id']} port={HY2_PORT} proto={again.get('protocol')}")
    return int(again["id"])


def sync_clients(inbound_id: int, src_clients: list, dry_run: bool) -> None:
    """auth = VLESS UUID, чтобы Happ JSON и сервер совпали."""
    by_email = {}
    for c in src_clients:
        email = (c.get("email") or "").strip()
        uuid = (c.get("id") or "").strip()
        if not email or not uuid:
            continue
        copy = {
            "auth": uuid,
            "email": email,
            "enable": bool(c.get("enable", True)),
            "expiryTime": c.get("expiryTime") or 0,
            "limitIp": int(c.get("limitIp") or 0),
            "totalGB": int(c.get("totalGB") or 0),
            "subId": c.get("subId") or "",
            "tgId": c.get("tgId") or 0,
            "comment": c.get("comment") or "",
            "reset": int(c.get("reset") or 0),
        }
        by_email[email] = copy
    clients = list(by_email.values())
    if dry_run:
        print(f"DRY sync {len(clients)} hy2 clients (auth=uuid)")
        return

    r = xui.session.get(f"{xui.base_url}/panel/api/inbounds/get/{inbound_id}", timeout=20)
    data = xui._parse_response(r)
    if not data.get("success"):
        print("FAIL get hy2 inbound", data, file=sys.stderr)
        sys.exit(1)
    ib = data["obj"]
    settings = json.loads(ib.get("settings") or "{}")
    settings["version"] = 2
    settings["clients"] = clients
    ib["settings"] = json.dumps(settings, ensure_ascii=False)
    r2 = xui.session.post(
        f"{xui.base_url}/panel/api/inbounds/update/{inbound_id}",
        json=ib,
        timeout=60,
    )
    data2 = xui._parse_response(r2)
    if not data2.get("success"):
        print("FAIL update hy2 clients", data2, file=sys.stderr)
        sys.exit(1)
    print(f"  inbound settings: {len(clients)} clients")

    # x-ui 3.7: client_inbounds — иначе панель «теряет» привязки
    db = sqlite3.connect(XUI_DB)
    rows = db.execute("SELECT id, email, uuid FROM clients").fetchall()
    email_to_id = {str(e): int(i) for i, e, _u in rows}
    now_ms = int(__import__("time").time() * 1000)
    attached = 0
    for email, c in by_email.items():
        cid = email_to_id.get(email)
        if not cid:
            continue
        exists = db.execute(
            "SELECT 1 FROM client_inbounds WHERE client_id=? AND inbound_id=?",
            (cid, inbound_id),
        ).fetchone()
        if exists:
            continue
        db.execute(
            "INSERT INTO client_inbounds (client_id, inbound_id, flow_override, created_at) VALUES (?,?,?,?)",
            (cid, inbound_id, "", now_ms),
        )
        attached += 1
    db.commit()
    db.close()
    print(f"  client_inbounds inserted: {attached}")
    xui.restart_xray()


def patch_env(inbound_id: int) -> None:
    updates = {
        "AMS_HY2_PORT": str(HY2_PORT),
        "AMS_HY2_SNI": HY2_SNI,
        "AMS_HY2_HOST": HY2_SNI,
        "HYSTERIA_PUBLIC_HOST": HY2_SNI,
        "HYSTERIA_PORT": str(HY2_PORT),
        "HYSTERIA_SNI": HY2_SNI,
        "HYSTERIA_INBOUND_ID": str(inbound_id),
        "VPN_PROFILE_AMS_HYSTERIA": "🇪🇺 Hysteria",
    }
    for env_path in ENV_PATHS:
        p = Path(env_path)
        if not p.exists():
            continue
        lines = p.read_text(encoding="utf-8").splitlines()
        idx = {
            line.split("=", 1)[0]: i
            for i, line in enumerate(lines)
            if "=" in line and not line.strip().startswith("#")
        }
        file_updates = dict(updates)
        if "NL_XUI_INBOUND_IDS" in idx:
            current = lines[idx["NL_XUI_INBOUND_IDS"]].split("=", 1)[1].strip()
            ids = [x.strip() for x in current.split(",") if x.strip()]
            if str(inbound_id) not in ids:
                ids.append(str(inbound_id))
            file_updates["NL_XUI_INBOUND_IDS"] = ",".join(ids)
        for key, val in file_updates.items():
            line = f"{key}={val}"
            if key in idx:
                lines[idx[key]] = line
            else:
                lines.append(line)
        p.write_text("\n".join(lines) + "\n", encoding="utf-8")
        print(f"  env updated: {env_path}")


def ensure_files() -> None:
    if not Path(CERT_FILE).is_file() or not Path(KEY_FILE).is_file():
        print(f"FAIL: cert/key missing:\n  {CERT_FILE}\n  {KEY_FILE}", file=sys.stderr)
        sys.exit(1)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--skip-env", action="store_true")
    args = ap.parse_args()
    ensure_files()
    if not xui._ensure_auth() and not args.dry_run:
        print("FAIL: x-ui login", file=sys.stderr)
        sys.exit(1)

    r = xui.session.get(f"{xui.base_url}/panel/api/inbounds/get/{SRC_INBOUND_ID}", timeout=20)
    data = xui._parse_response(r)
    if not data.get("success"):
        print("FAIL get source inbound", data, file=sys.stderr)
        sys.exit(1)
    src_clients = parse_clients(data["obj"])
    print(f"=== Hysteria2 UDP :{HY2_PORT} SNI={HY2_SNI} ===")
    print(f"  cert: {CERT_FILE}")
    print(f"  clients to copy: {len(src_clients)}")

    new_id = create_inbound(args.dry_run)
    if new_id and not args.dry_run:
        sync_clients(new_id, src_clients, False)
        if not args.skip_env:
            patch_env(new_id)
        print(f"\nOK: HYSTERIA_INBOUND_ID={new_id} AMS_HY2_PORT={HY2_PORT}")
    elif args.dry_run:
        print(f"Would sync {len(src_clients)} clients to Hysteria2 :{HY2_PORT}")


if __name__ == "__main__":
    main()
