#!/usr/bin/env python3
"""Point wingsvpn.shop / www off dead Frankfurt onto Amsterdam.

Frankfurt origin 172.86.68.87 is unreachable, so orange-cloud
https://wingsvpn.shop returns Cloudflare 523. Amsterdam
107.189.22.142 already has the Let's Encrypt cert and proxies
HTTP to 4VPS :80. Do not point orange-cloud at 4VPS :443 (Reality).

Requires CLOUDFLARE_API_TOKEN with Zone.DNS Edit and Zone.SSL Edit.

  CLOUDFLARE_API_TOKEN=... python3 infra/cloudflare/point_apex_to_ams.py --dry-run
  CLOUDFLARE_API_TOKEN=... python3 infra/cloudflare/point_apex_to_ams.py --apply
"""
from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request

ZONE_NAME = "wingsvpn.shop"
AMS_A = "107.189.22.142"
AMS_AAAA = "2602:fa59:5:5a8::1"
HOSTS = ("wingsvpn.shop", "www.wingsvpn.shop")
API = "https://api.cloudflare.com/client/v4"


def _token() -> str:
    tok = (os.getenv("CLOUDFLARE_API_TOKEN") or "").strip()
    if not tok:
        sys.exit("CLOUDFLARE_API_TOKEN is empty")
    return tok


def cf(method: str, path: str, token: str, payload: dict | None = None) -> dict:
    data = None if payload is None else json.dumps(payload).encode()
    req = urllib.request.Request(
        API + path,
        data=data,
        method=method,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            body = json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        detail = e.read().decode()[:500]
        raise SystemExit(f"{method} {path} -> {e.code} {detail}") from e
    if not body.get("success"):
        raise SystemExit(f"{method} {path} failed: {body.get('errors')}")
    return body


def upsert_record(
    token: str,
    zone_id: str,
    *,
    name: str,
    rtype: str,
    content: str,
    apply: bool,
) -> None:
    qs = urllib.parse.urlencode({"name": name, "type": rtype, "per_page": 100})
    recs = cf("GET", f"/zones/{zone_id}/dns_records?{qs}", token).get("result") or []
    wanted = {
        "type": rtype,
        "name": name,
        "content": content,
        "ttl": 1,
        "proxied": True,
    }
    if recs:
        rec = recs[0]
        same = (
            rec.get("content") == content
            and rec.get("proxied") is True
            and rec.get("type") == rtype
        )
        extra = recs[1:]
        print(
            f"{'keep' if same else 'update'} {rtype} {name} "
            f"{rec.get('content')} -> {content} proxied={rec.get('proxied')}"
        )
        if apply and not same:
            cf("PUT", f"/zones/{zone_id}/dns_records/{rec['id']}", token, wanted)
        for extra_rec in extra:
            print(f"delete extra {rtype} {name} {extra_rec.get('content')}")
            if apply:
                cf("DELETE", f"/zones/{zone_id}/dns_records/{extra_rec['id']}", token)
        return
    print(f"create {rtype} {name} {content}")
    if apply:
        cf("POST", f"/zones/{zone_id}/dns_records", token, wanted)


def main() -> int:
    apply = "--apply" in sys.argv
    if not apply and "--dry-run" not in sys.argv:
        print("need --dry-run or --apply", file=sys.stderr)
        return 2
    token = _token()
    zones = cf("GET", f"/zones?name={ZONE_NAME}", token).get("result") or []
    if not zones:
        raise SystemExit(f"zone {ZONE_NAME} not found")
    zone_id = zones[0]["id"]
    print("zone", zone_id, zones[0].get("name"), "apply", apply)

    ssl = cf("GET", f"/zones/{zone_id}/settings/ssl", token).get("result") or {}
    print("ssl", ssl.get("value"))
    if ssl.get("value") not in ("full", "strict"):
        print("ssl -> full")
        if apply:
            cf("PATCH", f"/zones/{zone_id}/settings/ssl", token, {"value": "full"})

    for host in HOSTS:
        upsert_record(token, zone_id, name=host, rtype="A", content=AMS_A, apply=apply)
        upsert_record(token, zone_id, name=host, rtype="AAAA", content=AMS_AAAA, apply=apply)
    print("done")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
