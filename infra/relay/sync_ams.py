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


def _reality_clients(clients: list[dict], flow: str = "") -> list[dict]:
    out = []
    for c in clients:
        entry = {"id": c["id"], "email": c["email"]}
        if flow:
            entry["flow"] = flow
        out.append(entry)
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


def main() -> int:
    params = load_params()
    host = params["host"]
    clients = all_clients()
    sync_hysteria_allowlist(host, clients)
    cfg = render_config(params, clients)
    blob = json.dumps(cfg, indent=2, ensure_ascii=False)
    digest = hashlib.sha256(blob.encode()).hexdigest()

    cached = ""
    if os.path.exists(CACHE):
        with open(CACHE) as f:
            cached = f.read().strip()
    if digest == cached:
        print(f"no change ({len(clients)} clients, 3 inbounds)")
        return 0

    tmp = "/tmp/ams_config.json"
    with open(tmp, "w") as f:
        f.write(blob)
    r = scp(host, tmp, REMOTE_STAGING)
    if r.returncode != 0:
        print("scp failed:", r.stderr, file=sys.stderr)
        return 1
    test = ssh(host, f"/usr/local/bin/xray -test -c {REMOTE_STAGING}")
    if test.returncode != 0:
        print("xray -test failed:", test.stdout, test.stderr, file=sys.stderr)
        ssh(host, f"rm -f {REMOTE_STAGING}")
        return 1
    ssh(host, f"mv {REMOTE_STAGING} {REMOTE_CFG} && systemctl restart xray")
    with open(CACHE, "w") as f:
        f.write(digest)
    print(
        f"updated -> {len(clients)} clients, "
        f"tcp:{params.get('xray_port', 10443)} "
        f"grpc:{params.get('grpc_port', 49713)} "
        f"grpc2:{params.get('grpc2_port', 41028)} on {host}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
