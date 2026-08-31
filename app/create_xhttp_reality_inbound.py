#!/usr/bin/env python3
"""
Создать inbound VLESS + XHTTP + Reality на публичном TCP 8443.

Копирует Reality-ключи с TCP inbound (id=2), клиентов — через
POST /panel/api/clients/bulkAttach. flow пустой (Vision только на TCP :443).

  cd /opt/nordwings/app
  ./venv/bin/python create_xhttp_reality_inbound.py --dry-run
  ./venv/bin/python create_xhttp_reality_inbound.py
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, "/opt/nordwings/app")
os.chdir("/opt/nordwings/app")

from bot_api import xui  # noqa: E402

XHTTP_PORT = int(os.getenv("AMS_XHTTP_PORT", os.getenv("XHTTP_REALITY_PORT", "8443")))
XHTTP_PATH = os.getenv("AMS_XHTTP_PATH", "/")
XHTTP_MODE = os.getenv("AMS_XHTTP_SERVER_MODE", "auto")
XHTTP_TAG = os.getenv("AMS_XHTTP_INBOUND_TAG", "inbound-xhttp-reality")
SRC_INBOUND_ID = int(os.getenv("TCP_INBOUND_ID", "2"))
ENV_PATHS = ("/opt/nordwings/app/.env", "/opt/nordwings-web/.env")


def parse_stream(inbound: dict) -> dict:
    raw = inbound.get("streamSettings") or "{}"
    return json.loads(raw) if isinstance(raw, str) else dict(raw or {})


def parse_clients(inbound: dict) -> list:
    raw = inbound.get("settings") or "{}"
    settings = json.loads(raw) if isinstance(raw, str) else raw
    return list(settings.get("clients") or [])


def build_xhttp_stream(tcp_stream: dict) -> dict:
    rs = dict(tcp_stream.get("realitySettings") or {})
    settings = dict(rs.get("settings") or {})
    if not settings.get("spiderX"):
        settings["spiderX"] = "/"
    rs["settings"] = settings
    if rs.get("show") is None:
        rs["show"] = False
    return {
        "network": "xhttp",
        "security": "reality",
        "externalProxy": tcp_stream.get("externalProxy") or [],
        "realitySettings": rs,
        "xhttpSettings": {
            "path": XHTTP_PATH or "/",
            "host": "",
            "mode": XHTTP_MODE or "auto",
        },
        "sockopt": tcp_stream.get("sockopt") or {
            "tcpFastOpen": True,
            "tcpNoDelay": True,
            "tcpKeepAliveInterval": 30,
        },
    }


def inbound_by_port(port: int) -> dict | None:
    if not xui._ensure_auth():
        return None
    r = xui.session.get(f"{xui.base_url}/panel/api/inbounds/list", timeout=15)
    data = xui._parse_response(r)
    for ib in data.get("obj") or []:
        if int(ib.get("port") or 0) == port:
            return ib
        remark = (ib.get("remark") or "").lower()
        if "xhttp" in remark and "reality" in remark:
            return ib
    return None


def create_inbound(stream: dict, dry_run: bool) -> int | None:
    existing = inbound_by_port(XHTTP_PORT)
    if existing:
        print(f"  inbound already exists id={existing.get('id')} port={existing.get('port')}")
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
        "remark": "NL XHTTP Reality",
        "enable": True,
        "expiryTime": 0,
        "listen": "",
        "port": XHTTP_PORT,
        "protocol": "vless",
        "settings": json.dumps({"clients": [], "decryption": "none", "fallbacks": []}),
        "streamSettings": json.dumps(stream, ensure_ascii=False),
        "sniffing": json.dumps(sniffing, ensure_ascii=False),
        "allocate": json.dumps({"strategy": "always", "refresh": 5, "concurrency": 3}),
    }
    if dry_run:
        redacted = json.loads(payload["streamSettings"])
        if "realitySettings" in redacted:
            redacted["realitySettings"] = {
                k: ("<redacted>" if k == "privateKey" else v)
                for k, v in (redacted["realitySettings"] or {}).items()
            }
        print("DRY create inbound port", XHTTP_PORT)
        print(json.dumps({**payload, "streamSettings": redacted}, ensure_ascii=False, indent=2)[:2500])
        return None

    r = xui.session.post(f"{xui.base_url}/panel/api/inbounds/add", json=payload, timeout=20)
    data = xui._parse_response(r)
    if not data.get("success"):
        print("FAIL add inbound:", data, file=sys.stderr)
        sys.exit(1)
    again = inbound_by_port(XHTTP_PORT)
    if not again:
        print("FAIL: inbound not found after create", data, file=sys.stderr)
        sys.exit(1)
    print(f"  created inbound id={again['id']} port={XHTTP_PORT}")
    return int(again["id"])


def bulk_attach(inbound_id: int, emails: list[str], dry_run: bool) -> None:
    emails = [e for e in emails if e]
    if dry_run:
        print(f"DRY bulkAttach {len(emails)} emails -> inbound {inbound_id}")
        return
    r = xui.session.post(
        f"{xui.base_url}/panel/api/clients/bulkAttach",
        json={"emails": emails, "inboundIds": [inbound_id]},
        timeout=120,
    )
    data = xui._parse_response(r)
    if not data.get("success"):
        print("FAIL bulkAttach:", data, file=sys.stderr)
        sys.exit(1)
    obj = data.get("obj") if isinstance(data.get("obj"), dict) else {}
    attached = obj.get("attached") or []
    skipped = obj.get("skipped") or []
    errors = obj.get("errors") or []
    print(
        f"  bulkAttach inbound {inbound_id}: "
        f"attached={len(attached)} skipped={len(skipped)} errors={len(errors)}"
    )
    if errors:
        print("  first errors:", errors[:5], file=sys.stderr)


def patch_env(inbound_id: int) -> None:
    updates = {
        "AMS_XHTTP_PORT": str(XHTTP_PORT),
        "AMS_XHTTP_PATH": XHTTP_PATH or "/",
        "AMS_XHTTP_MODE": "stream-up",
        "AMS_XHTTP_FP": "chrome",
        "XHTTP_REALITY_INBOUND_ID": str(inbound_id),
    }
    for env_path in ENV_PATHS:
        p = Path(env_path)
        if not p.exists():
            continue
        lines = p.read_text(encoding="utf-8").splitlines()
        idx = {line.split("=", 1)[0]: i for i, line in enumerate(lines) if "=" in line and not line.strip().startswith("#")}
        file_updates = dict(updates)
        if "NL_XUI_INBOUND_IDS" in idx:
            current_ids = lines[idx["NL_XUI_INBOUND_IDS"]].split("=", 1)[1].strip()
            ids = [x.strip() for x in current_ids.split(",") if x.strip()]
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
        extra = (
            f" NL_XUI_INBOUND_IDS={file_updates['NL_XUI_INBOUND_IDS']}"
            if "NL_XUI_INBOUND_IDS" in file_updates
            else ""
        )
        print(f"  env updated: {env_path}{extra}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--skip-env", action="store_true")
    args = ap.parse_args()

    if not xui._ensure_auth() and not args.dry_run:
        print("FAIL: x-ui login", file=sys.stderr)
        sys.exit(1)

    r = xui.session.get(f"{xui.base_url}/panel/api/inbounds/get/{SRC_INBOUND_ID}", timeout=20)
    data = xui._parse_response(r)
    if not data.get("success"):
        print("FAIL get source inbound", data, file=sys.stderr)
        sys.exit(1)
    src = data["obj"]
    tcp_stream = parse_stream(src)
    clients = parse_clients(src)
    emails = [str(c.get("email") or "").strip() for c in clients]
    emails = [e for e in emails if e]
    stream = build_xhttp_stream(tcp_stream)
    rs = stream["realitySettings"]
    print(f"=== XHTTP Reality inbound port={XHTTP_PORT} path={XHTTP_PATH} mode={XHTTP_MODE} ===")
    print(f"  dest/SNI: {rs.get('dest') or rs.get('target')} / {rs.get('serverNames')}")
    print(f"  shortIds: {rs.get('shortIds')}")
    print(f"  clients to attach: {len(emails)}")

    new_id = create_inbound(stream, args.dry_run)
    if new_id and not args.dry_run:
        bulk_attach(new_id, emails, False)
        if not args.skip_env:
            patch_env(new_id)
        xui.restart_xray()
        print(f"\nOK: XHTTP_REALITY_INBOUND_ID={new_id} AMS_XHTTP_PORT={XHTTP_PORT}")
    elif args.dry_run:
        print(f"Would attach {len(emails)} clients to new XHTTP inbound on :{XHTTP_PORT}")


if __name__ == "__main__":
    main()
