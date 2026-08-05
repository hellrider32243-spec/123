# Amsterdam clean-IP Reality relay

A dedicated second server on a **clean (non-blocked, non-Cloudflare) IP** running
VLESS + TCP + Reality (`xtls-rprx-vision`) directly on `:443`. This mirrors what
the competitor does and survives RU mobile-carrier IP blocking of the main
server, because the traffic is indistinguishable from ordinary HTTPS to a real
site (masking SNI `www.apple.com`, TLS 1.3, local CDN edge).

Unlike the main server, the relay runs Xray bound to `:443` directly (no nginx
in front), so it is immune to the nginx file-descriptor exhaustion that affected
the main node.

## Components

- **Relay host** (`AMS_HOST`): standalone Xray (`/usr/local/etc/xray/config.json`)
  installed via the official XTLS installer, `xray.service` (`LimitNOFILE=1000000`).
  Firewall (ufw) allows only `22` and `443`.
- **`sync_ams.py`** (runs on the MAIN server): reads the union of client UUIDs
  from `x-ui.db`, renders the relay Xray config (one VLESS TCP Reality inbound
  serving every subscriber with `flow=xtls-rprx-vision`), remotely `xray -test`s
  it and restarts the relay **only when the client set changed**. Pushes over SSH
  using the main server's key. Reality secrets live in `ams.params.json`
  (see `ams.params.example.json`), never in the repo.
- **`ams-sync.service` + `ams-sync.timer`**: run `sync_ams.py` every 120 s so new
  and renewing users are provisioned on the relay automatically.

## Hysteria2 (second profile)

The relay also runs a standalone **Hysteria2** server (UDP/QUIC) on `:8447` for
lossy LTE/4G, on the same clean IP:

- Binary `/usr/local/bin/hysteria`, config `/etc/hysteria/config.yaml`, unit
  `hysteria-server.service`.
- TLS: a real Let's Encrypt cert for `ams.wingsvpn.shop` (DNS-only A record →
  relay IP), so an active prober sees a valid cert for a real domain.
- Auth: `type: command` → `/etc/hysteria/hy2_check_auth.py`, which accepts a UUID
  present in `/etc/hysteria/allowed_uuids.txt`. The list is pushed by
  `sync_ams.py` (read fresh per auth attempt, so no restart on change).
- Masquerade: HTTP/3 proxy to `https://www.cloudflare.com`.

## Subscription wiring

`app/happ_json_config.py` gains `build_amsterdam_reality_config(...)` (profile[0],
TCP Reality) and reuses `build_hysteria_lte_config(...)` pointed at
`AMS_HYSTERIA_HOST` (profile[1], Hysteria2). `build_happ_json_subscription` now
returns **only these two clean-IP profiles**, each guarded by its env
(`AMS_HOST`+`AMS_PBK`, and `AMS_HYSTERIA_HOST`).

Hysteria env (both `.env` files):

```
AMS_HYSTERIA_HOST=ams.wingsvpn.shop
AMS_HYSTERIA_PORT=8447
AMS_HYSTERIA_SNI=ams.wingsvpn.shop
VPN_PROFILE_AMS_HYSTERIA=🇳🇱 Amsterdam — 📡 Hysteria
```

Relevant env (main `.env` and `/opt/nordwings-web/.env`):

```
AMS_HOST=<relay public IPv4>
AMS_PORT=443
AMS_PBK=<reality public key from `xray x25519`>
AMS_SID=<8 hex chars>
AMS_SNI=www.apple.com
AMS_FP=chrome
AMS_FLOW=xtls-rprx-vision
VPN_PROFILE_AMS=🇳🇱 Нидерланды — 🚀 Чистый
```

## Provisioning a new relay

1. Create an Ubuntu VPS on a clean IP (verify RU reachability with check-host first).
2. `apt install` + official Xray installer; `ufw allow 22,443`.
3. `xray x25519` for the keypair; `openssl rand -hex 4` for the shortId.
4. Put the main server's SSH public key in the relay's `authorized_keys`.
5. Fill `/opt/nordwings/relay/ams.params.json` from the example; run `sync_ams.py` once.
6. Set the `AMS_*` env vars in both `.env` files and restart `nordwings-web`.
7. Enable `ams-sync.timer` on the main server.
