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

## Subscription wiring

`app/happ_json_config.py` gains `build_amsterdam_reality_config(...)` and inserts
it as **profile[0]** (highest priority) in `build_happ_json_subscription`, guarded
by `AMS_HOST` + `AMS_PBK` so it is a no-op until the relay is configured.

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
