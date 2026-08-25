#!/usr/bin/env python3
"""Синхронизирует список клиентов WS-Xray (cf-ws) с union всех UUID из x-ui.
Перезапускает cf-ws только если набор изменился."""
import json, sqlite3, subprocess, sys

XUI_DB = "/etc/x-ui/x-ui.db"
WS_CFG = "/opt/nordwings/cf/ws.json"

def all_clients():
    c = sqlite3.connect(XUI_DB)
    try:
        rows = c.execute("SELECT settings FROM inbounds").fetchall()
    finally:
        c.close()
    seen = {}
    for (s,) in rows:
        try:
            for cl in json.loads(s).get("clients", []):
                uid = cl.get("id")
                if not uid:
                    continue
                if uid not in seen:
                    seen[uid] = cl.get("email") or uid
        except Exception:
            continue
    return [{"id": u, "email": e} for u, e in seen.items()]

def _inbound_ids(ib) -> list:
    return sorted(x.get("id") for x in (ib.get("settings") or {}).get("clients", []))


def main():
    cfg = json.load(open(WS_CFG))
    clients = all_clients()
    new_ids = sorted(x["id"] for x in clients)
    changed = False
    for ib in cfg.get("inbounds") or []:
        if _inbound_ids(ib) != new_ids:
            ib.setdefault("settings", {})["clients"] = clients
            changed = True
    if not changed:
        print(f"no change ({len(new_ids)} clients)")
        return 0
    json.dump(cfg, open(WS_CFG, "w"), indent=2)
    subprocess.run(["systemctl", "restart", "cf-ws.service"], check=False)
    print(f"updated -> {len(new_ids)} clients across {len(cfg.get('inbounds') or [])} inbounds, cf-ws restarted")
    return 0

if __name__ == "__main__":
    sys.exit(main())
