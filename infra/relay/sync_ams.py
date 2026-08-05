#!/usr/bin/env python3
"""Sync the standalone Amsterdam clean-IP Reality node with the union of x-ui
client UUIDs and push the rendered Xray config over SSH.

Runs on the MAIN server (has x-ui.db + SSH key to the relay). Renders a VLESS
TCP Reality (xtls-rprx-vision) inbound serving every current subscriber, tests
it remotely with `xray -test`, and restarts the relay only when the config
actually changed. Secrets (Reality private key, relay IP) live in
PARAMS_PATH, never in the repo.
"""
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


def render_config(params: dict, clients: list[dict]) -> dict:
    flow = params.get("flow", "xtls-rprx-vision")
    sni = params["sni"]
    return {
        "log": {"loglevel": "warning"},
        "inbounds": [
            {
                "listen": "0.0.0.0",
                "port": int(params.get("port", 443)),
                "protocol": "vless",
                "settings": {
                    "clients": [
                        {"id": c["id"], "flow": flow, "email": c["email"]}
                        for c in clients
                    ],
                    "decryption": "none",
                },
                "streamSettings": {
                    "network": "tcp",
                    "security": "reality",
                    "realitySettings": {
                        "show": False,
                        "dest": f"{sni}:443",
                        "xver": 0,
                        "serverNames": [sni],
                        "privateKey": params["privateKey"],
                        "shortIds": ["", params["shortId"]],
                    },
                },
                "sniffing": {
                    "enabled": True,
                    "destOverride": ["http", "tls", "quic"],
                },
            }
        ],
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
    """Push the UUID allow-list for the relay Hysteria2 auth command.
    The auth script reads it fresh per attempt, so no restart is needed."""
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

    remote_hash = ssh(host, f"sha256sum {REMOTE_CFG} 2>/dev/null | cut -d' ' -f1").stdout.strip()
    local_of_remote = ""
    # Compare against a locally cached digest of what we last pushed.
    cache = "/opt/nordwings/relay/.ams_last_sha"
    if os.path.exists(cache):
        with open(cache) as f:
            local_of_remote = f.read().strip()
    if digest == local_of_remote and remote_hash:
        print(f"no change ({len(clients)} clients)")
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
    with open(cache, "w") as f:
        f.write(digest)
    print(f"updated -> {len(clients)} clients on {host}, xray restarted")
    return 0


if __name__ == "__main__":
    sys.exit(main())
