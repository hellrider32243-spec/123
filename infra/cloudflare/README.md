# Cloudflare fronting for NordWings VPN

## Why

Russian ISPs (especially mobile carriers) block the VPS IP `172.86.68.87` at the
network/DPI level. From several Russian networks a plain TCP connect to the server
times out on every port, so the VPN "connects then dies". This is not fixable by
tweaking Xray/Nginx — the server itself is healthy.

The fix routes clients to Cloudflare's anycast IPs (which Russian networks do not
mass-block) via a Cloudflare Tunnel, using a clean SNI on the customer domain
(`cf.wingsvpn.shop`) instead of a flagged tunnel domain.

## Data path

```
Client (Happ)  --TLS/WS :443, SNI=cf.wingsvpn.shop-->  Cloudflare edge (anycast)
   --QUIC tunnel-->  cloudflared on VPS  --http://127.0.0.1:8880-->  Xray VLESS-WS
   --freedom-->  Internet
```

## Components (deployed on the VPS)

- **`cf-ws.service`** — standalone Xray, VLESS + WebSocket inbound on
  `127.0.0.1:8880`, path `/cfws`, no TLS (Cloudflare terminates TLS at the edge).
  Config: `/opt/nordwings/cf/ws.json` (see `ws.template.json` for the shape).
- **`cloudflared-nordwings.service`** — Cloudflare Tunnel `nordwings-cf`. Ingress
  `cf.wingsvpn.shop -> http://127.0.0.1:8880`. Tunnel token stored root-only at
  `/etc/cloudflared/nordwings-token` (NOT in git).
- **`sync_ws_clients.py`** + **`cf-ws-sync.timer`** — every ~2 min, syncs the WS
  inbound client list to the union of all client UUIDs across the x-ui inbounds,
  restarting `cf-ws` only when the set changes. This makes the Cloudflare profile
  work for every subscriber automatically.

## Cloudflare objects (managed via API)

- Zone `wingsvpn.shop` (NS moved from Porkbun to Cloudflare).
- Tunnel `nordwings-cf`, remotely-managed config (`config_src=cloudflare`).
- DNS `cf.wingsvpn.shop` = CNAME → `<tunnel-id>.cfargotunnel.com`, **proxied**.

## Subscription integration

`happ_json_config.py`:
- `_ws_outbound()` builds the VLESS+WS+TLS outbound.
- `build_cloudflare_ws_config()` builds the Happ profile
  (`☁️ Cloudflare — обход блокировок`).
- It is inserted as the **first / highest-priority** profile in
  `build_happ_json_subscription()`.

Environment overrides (optional): `CF_WS_HOST`, `CF_WS_PORT`, `CF_WS_PATH`,
`CF_WS_SNI`, `CF_WS_FP`, `VPN_PROFILE_CF`.
