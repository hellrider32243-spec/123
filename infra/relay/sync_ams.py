#!/usr/bin/env python3
"""Sync the Amsterdam clean-IP Reality node with x-ui client UUIDs.

Renders Ultima-style inbounds on the relay:
  - TCP Reality (xtls-rprx-vision) on 127.0.0.1:10443  (nginx stream :443 → here)
  - gRPC Reality on 0.0.0.0:49713  (SNI apple.com)   — like Ultima «Нидерланды»
  - gRPC Reality on 0.0.0.0:41028  (SNI deepl.com)   — like Ultima «Hysteria» / NL#2

Pushes over SSH; restarts xray only when the config changes. Also syncs the
Hysteria2 UUID allow-list (optional real hy2 on :8447).
"""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys

XUI_DB = os.getenv("XUI_DB_PATH", "/etc/x-ui/x-ui.db")
PARAMS_PATH = os.getenv("AMS_PARAMS_PATH", "/opt/nordwings/relay/ams.params.json")
SSH_KEY = os.getenv("AMS_SSH_KEY", "/root/.ssh/id_ed25519")
REMOTE_CFG = "/usr/local/etc/xray/config.json"
REMOTE_STAGING = "/usr/local/etc/xray/config.staging.json"
REMOTE_HY_ALLOW = "/etc/hysteria/allowed_uuids.txt"
CACHE = "/opt/nordwings/relay/.ams_last_sha"
HY_CACHE = "/opt/nordwings/relay/.ams_hy_last_sha"
SSH_OPTS = [
    "-o", "StrictHostKeyChecking=no",
    "-o", "ConnectTimeout=10",
    "-o", "BatchMode=yes",
]


def load_params() -> dict:
    with open(PARAMS_PATH) as f:
        return json.load(f)


def all_clients() -> list[dict]:
    import sqlite3

    con = sqlite3.connect(XUI_DB)
    try:
        rows = con.execute("SELECT settings FROM inbounds").fetchall()
    finally:
        con.close()
    seen: dict[str, str] = {}
    for (settings,) in rows:
        try:
            for cl in json.loads(settings).get("clients", []):
                uid = cl.get("id")
                if uid and uid not in seen:
                    seen[uid] = cl.get("email") or uid
        except Exception:
            continue
    return [{"id": u, "email": e} for u, e in seen.items()]


LIMIT_IP = int(os.getenv("VPN_DEVICE_LIMIT_IP", os.getenv("VPN_MAX_DEVICES", "3")) or "3")
# AMS Reality inbounds are managed by x-ui (limitIp enforcement). Standalone xray disabled.
# TCP :443 goes nginx(stream)+proxy_protocol -> 127.0.0.1:10443 (acceptProxyProtocol=true).
AMS_XUI_PORTS = (
    int(os.getenv("AMS_XRAY_PORT", "10443")),
    int(os.getenv("AMS_GRPC_PORT", "49713")),
    int(os.getenv("AMS_GRPC2_PORT", "41028")),
)


def _reality_clients(clients: list[dict], flow: str = "") -> list[dict]:
    out = []
    for c in clients:
        entry = {"id": c["id"], "email": c["email"]}
        if flow:
            entry["flow"] = flow
        out.append(entry)
    return out


def _xui_clients(clients: list[dict], flow: str = "") -> list[dict]:
    """Clients for AMS x-ui inbounds — include limitIp for device cap."""
    out = []
    for c in clients:
        out.append(
            {
                "id": c["id"],
                "email": c["email"],
                "enable": True,
                "limitIp": max(1, LIMIT_IP),
                "totalGB": 0,
                "expiryTime": 0,
                "reset": 0,
                "flow": flow or "",
                "tgId": "",
                "subId": "",
                "comment": "",
            }
        )
    return out


def render_config(params: dict, clients: list[dict]) -> dict:
    flow = params.get("flow", "xtls-rprx-vision")
    priv = params["privateKey"]
    sid = params["shortId"]
    sid2 = params.get("shortId2") or sid
    tcp_sni = params.get("sni", "www.apple.com")
    grpc_sni = params.get("grpc_sni", "apple.com")
    grpc2_sni = params.get("grpc2_sni", "deepl.com")
    grpc_port = int(params.get("grpc_port", 49713))
    grpc2_port = int(params.get("grpc2_port", 41028))
    grpc_service = params.get("grpc_service", "ws")
    grpc2_service = params.get("grpc2_service", "deepl")
    xray_port = int(params.get("xray_port", 10443))

    def reality_settings(server_names: list[str], dest: str, short_id: str) -> dict:
        return {
            "show": False,
            "dest": dest,
            "xver": 0,
            "serverNames": server_names,
            "privateKey": priv,
            "shortIds": ["", short_id],
        }

    inbounds = [
        # TCP Reality behind nginx stream (public :443)
        {
            "tag": "ams-tcp",
            "listen": params.get("listen", "127.0.0.1"),
            "port": xray_port,
            "protocol": "vless",
            "settings": {
                "clients": _reality_clients(clients, flow=flow),
                "decryption": "none",
            },
            "streamSettings": {
                "network": "tcp",
                "security": "reality",
                "realitySettings": reality_settings(
                    [tcp_sni, "apple.com", "www.apple.com"],
                    f"{tcp_sni}:443",
                    sid,
                ),
            },
            "sniffing": {
                "enabled": True,
                "destOverride": ["http", "tls", "quic"],
            },
        },
        # gRPC Reality — Ultima «Нидерланды»
        {
            "tag": "ams-grpc",
            "listen": "0.0.0.0",
            "port": grpc_port,
            "protocol": "vless",
            "settings": {
                "clients": _reality_clients(clients, flow=""),
                "decryption": "none",
            },
            "streamSettings": {
                "network": "grpc",
                "grpcSettings": {"serviceName": grpc_service},
                "security": "reality",
                "realitySettings": reality_settings(
                    [grpc_sni, "www.apple.com", "apple.com"],
                    f"{grpc_sni}:443",
                    sid,
                ),
            },
            "sniffing": {
                "enabled": True,
                "destOverride": ["http", "tls", "quic"],
            },
        },
        # gRPC Reality #2 — Ultima «Hysteria» / NL#2 style
        {
            "tag": "ams-grpc2",
            "listen": "0.0.0.0",
            "port": grpc2_port,
            "protocol": "vless",
            "settings": {
                "clients": _reality_clients(clients, flow=""),
                "decryption": "none",
            },
            "streamSettings": {
                "network": "grpc",
                "grpcSettings": {"serviceName": grpc2_service},
                "security": "reality",
                "realitySettings": reality_settings(
                    [grpc2_sni, f"www.{grpc2_sni}"],
                    f"{grpc2_sni}:443",
                    sid2,
                ),
            },
            "sniffing": {
                "enabled": True,
                "destOverride": ["http", "tls", "quic"],
            },
        },
    ]
    return {
        "log": {"loglevel": "warning"},
        "inbounds": inbounds,
        "outbounds": [
            {"protocol": "freedom", "tag": "direct"},
            {"protocol": "blackhole", "tag": "block"},
        ],
        "routing": {
            "rules": [
                {"type": "field", "ip": ["geoip:private"], "outboundTag": "block"},
                {"type": "field", "protocol": ["bittorrent"], "outboundTag": "block"},
            ]
        },
    }


def ssh(host: str, cmd: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["ssh", "-i", SSH_KEY, *SSH_OPTS, f"root@{host}", cmd],
        capture_output=True,
        text=True,
    )


def scp(host: str, local: str, remote: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["scp", "-i", SSH_KEY, *SSH_OPTS, local, f"root@{host}:{remote}"],
        capture_output=True,
        text=True,
    )


def sync_hysteria_allowlist(host: str, clients: list[dict]) -> None:
    blob = "\n".join(sorted(c["id"] for c in clients)) + "\n"
    digest = hashlib.sha256(blob.encode()).hexdigest()
    cached = ""
    if os.path.exists(HY_CACHE):
        with open(HY_CACHE) as f:
            cached = f.read().strip()
    if digest == cached:
        return
    tmp = "/tmp/ams_allowed_uuids.txt"
    with open(tmp, "w") as f:
        f.write(blob)
    r = scp(host, tmp, REMOTE_HY_ALLOW)
    if r.returncode != 0:
        print("hysteria allowlist scp failed:", r.stderr, file=sys.stderr)
        return
    with open(HY_CACHE, "w") as f:
        f.write(digest)
    print(f"hysteria allow-list updated -> {len(clients)} uuids on {host}")


def sync_ams_xui_clients(host: str, params: dict, clients: list[dict]) -> bool:
    """Push UUID list + limitIp into AMS x-ui Reality inbounds and reload x-ui."""
    flow = params.get("flow", "xtls-rprx-vision")
    ports = {
        int(params.get("xray_port", AMS_XUI_PORTS[0])): _xui_clients(clients, flow=flow),
        int(params.get("grpc_port", AMS_XUI_PORTS[1])): _xui_clients(clients, flow=""),
        int(params.get("grpc2_port", AMS_XUI_PORTS[2])): _xui_clients(clients, flow=""),
    }
    payload = {str(p): cl for p, cl in ports.items()}
    blob = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    digest = hashlib.sha256(blob.encode()).hexdigest()
    cached = ""
    if os.path.exists(CACHE):
        with open(CACHE) as f:
            cached = f.read().strip()
    if digest == cached:
        print(f"no change ({len(clients)} clients, x-ui limitIp={LIMIT_IP})")
        return False

    tmp = "/tmp/ams_xui_clients_sync.json"
    with open(tmp, "w") as f:
        f.write(blob)
    r = scp(host, tmp, "/tmp/ams_xui_clients_sync.json")
    if r.returncode != 0:
        print("scp x-ui clients failed:", r.stderr, file=sys.stderr)
        return False

    remote_py = r'''
import json, sqlite3, sys
ports = json.load(open("/tmp/ams_xui_clients_sync.json"))
conn = sqlite3.connect("/etc/x-ui/x-ui.db")
changed = 0
for port_s, clients in ports.items():
    port = int(port_s)
    row = conn.execute("SELECT id, settings FROM inbounds WHERE port=?", (port,)).fetchone()
    if not row:
        print(f"missing inbound port={port}", file=sys.stderr)
        continue
    settings = json.loads(row[1] or "{}")
    settings["clients"] = clients
    conn.execute("UPDATE inbounds SET settings=?, enable=1 WHERE id=?", (json.dumps(settings, ensure_ascii=False), row[0]))
    changed += 1
conn.commit()
print(f"xui_updated={changed}")
'''
    upd = ssh(host, f"python3 - <<'PY'\n{remote_py}\nPY")
    if upd.returncode != 0:
        print("ams x-ui update failed:", upd.stdout, upd.stderr, file=sys.stderr)
        return False
    reload = ssh(host, "systemctl restart x-ui")
    if reload.returncode != 0:
        print("ams x-ui restart failed:", reload.stderr, file=sys.stderr)
        return False
    with open(CACHE, "w") as f:
        f.write(digest)
    print(
        f"updated x-ui -> {len(clients)} clients, limitIp={LIMIT_IP}, "
        f"tcp:{params.get('xray_port', 10443)} "
        f"grpc:{params.get('grpc_port', 49713)} "
        f"grpc2:{params.get('grpc2_port', 41028)} on {host}"
    )
    return True


def main() -> int:
    params = load_params()
    host = params["host"]
    clients = all_clients()
    sync_hysteria_allowlist(host, clients)
    # Reality traffic is on AMS x-ui (device limitIp). Keep a staging standalone
    # config on disk for emergency rollback, but do not restart standalone xray.
    cfg = render_config(params, clients)
    blob = json.dumps(cfg, indent=2, ensure_ascii=False)
    tmp = "/tmp/ams_config.json"
    with open(tmp, "w") as f:
        f.write(blob)
    scp(host, tmp, REMOTE_STAGING)
    sync_ams_xui_clients(host, params, clients)
    return 0


if __name__ == "__main__":
    sys.exit(main())
