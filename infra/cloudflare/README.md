# Cloudflare fronting for NordWings VPN

## Why

Russian ISPs (especially mobile carriers) block the origin VPS IPs
(`172.86.68.87` Frankfurt and `107.189.22.142` Amsterdam) at the network/DPI
level. Direct Reality to Apple SNI on those IPs often TCP-handshakes then dies
without an authenticated Xray session. That is not an Xray/Nginx crash — the
servers are healthy from outside Russia.

Two WS paths share the same Xray inbound (`127.0.0.1:8880`, path `/cfws`):

1. **Origin HTTPS (default for Happ)** — SNI `ams.wingsvpn.shop`. That hostname
   already works from Russia for subscription fetch (grey DNS, Let's Encrypt).
   nginx stream sends that SNI to `:8080`, which upgrades `/cfws` to Xray.
   Reality on the same IP is DPI'd; this looks like the working HTTPS site.
   RU mobile often presents **empty SNI** (ECH or TSPU). Stream `default` is
   nginx `:8080`, not Reality — otherwise those sessions stall with 0 bytes.
2. **Cloudflare anycast (fallback profile)** — SNI `cf.wingsvpn.shop` via Tunnel.
   Useful if the origin IP is fully blocked; some RU mobile networks never
   complete the tunnel handshake from the phone.

## Data path

```
# Origin (Happ Turbo / Нидерланды / Hysteria)
Client --TLS/WS :443, SNI=ams.wingsvpn.shop--> AMS nginx stream → :8080 /cfws
   --> Xray VLESS-WS :8880 --> freedom

# Cloudflare fallback (☁️ Cloudflare profile)
Client --TLS/WS :443, SNI=cf.wingsvpn.shop--> Cloudflare edge (anycast)
   --QUIC tunnel--> cloudflared --> Xray VLESS-WS :8880 --> freedom
```

## Components (deployed on the VPS)

- **`cf-ws.service`** — standalone Xray, VLESS + WebSocket inbound on
  `127.0.0.1:8880`, path `/cfws`, no TLS (Cloudflare terminates TLS at the edge).
  Config: `/opt/nordwings/cf/ws.json` (see `ws.template.json` for the shape).
- **`cloudflared-nordwings.service`** — Cloudflare Tunnel `nordwings-cf`. Ingress
  `cf.wingsvpn.shop -> http://127.0.0.1:8880`. Tunnel token stored root-only at
  `/etc/cloudflared/nordwings-token` (NOT in git).
- **`sync_ws_clients.py`** + **`cf-ws-sync.timer`** — every ~2 min, syncs every
  cf-ws inbound (WS `:8880` and XHTTP `:8881` if present) to the union of all
  client UUIDs across the x-ui inbounds, restarting `cf-ws` only when the set
  changes. This makes the Cloudflare profile work for every subscriber automatically.
  The timer must be enabled; without it new paying users get a CF profile whose
  UUID is missing on the tunnel inbound.

## Cloudflare objects (managed via API)

- Zone `wingsvpn.shop` (NS moved from Porkbun to Cloudflare).
- Tunnel `nordwings-cf`, remotely-managed config (`config_src=cloudflare`).
- DNS `cf.wingsvpn.shop` = CNAME → `<tunnel-id>.cfargotunnel.com`, **proxied**.

## Subscription integration

`happ_json_config.py`:
- `_ws_outbound()` builds the VLESS+WS+TLS outbound.
- Turbo / Нидерланды / Hysteria → origin `ams.wingsvpn.shop/cfws?ed=2560`.
- Named Cloudflare profile → `cf.wingsvpn.shop` (anycast fallback).

Environment overrides (optional): `CF_WS_HOST`, `CF_WS_PORT`, `CF_WS_PATH`,
`CF_WS_SNI`, `CF_WS_FP`, `CF_ORANGE_HOST`, `VPN_PROFILE_CF`.

nginx location: `infra/nginx/ams-cfws.location.conf` (live file is AMS
`/etc/nginx/nginx.conf`).
