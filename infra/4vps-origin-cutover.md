# 4VPS origin cutover (Frankfurt down → nLighten NL)

Frankfurt (`172.86.68.87`) is unreachable (`No route to host`), so Cloudflare
returns **523 Origin is unreachable** for `wingsvpn.shop`. VPN Reality stays on
4VPS `:443` — the site cannot bind that port.

## What now runs on 4VPS `139.28.240.160`

- x-ui + Xray Reality (`:443`, `:49714`, `:41028`) — unchanged
- `nordwings-web` `:8001` (Happ JSON `/sub/`)
- `nordwings` bot polling + API `:8081`
- nginx **HTTP `:80` only** → web/bot (see `4vps-http-origin.conf`)

JSON subscription already points at NL Reality (`139.28.240.160`, SNI `deepl.com`).

Happ `/miniapp/sub/{telegram_id}` must not depend on `keys` in `bot.db` alone:
x-ui can have the UUID while the bot copy from Frankfurt has no row (404).
Fallback: `app/xui_vless_lookup.py` builds NL TCP Reality from `clients.email = {id}_*`.
Backfill: `infra/backfill_nl_keys.py --apply --send`.

Do not issue `wingsvpn.shop:8443` / SNI `www.apple.com` / gRPC `log` — that was Frankfurt.

## HTTPS front

`https://ams.wingsvpn.shop` (grey-cloud to AMS nginx) proxies to 4VPS `:80`.
That host returns 200 for `/health` and `/miniapp/sub/{id}`.
Amsterdam nginx already serves `wingsvpn.shop` SNI (LE cert). Loopback check:
`https://wingsvpn.shop/health` on AMS = 200.

`https://wingsvpn.shop` public Internet: Cloudflare orange-cloud now origins to
Amsterdam (A `@`/`www` = `107.189.22.142`). `/health` and `/miniapp/sub` return 200.

All active `bot.db` keys already store `https://ams.wingsvpn.shop/miniapp/sub/{id}`
and NL Reality vless (`139.28.240.160`, not `:8443` / `www.apple.com`).

## Key issuance (4VPS x-ui)

This panel requires CSRF on every mutating API call (`X-CSRF-Token` on the session
after `GET /panel/` login, then refresh from `GET /panel/panel/`). New keys go
through `POST /panel/panel/api/clients/bulkCreate` on inbounds `1,2,3`; TCP
inbound 2 gets `xtls-rprx-vision` via `client_inbounds.flow_override`. Expiry
extend uses sqlite `clients.expiry_time` because classic `updateClient` is 404.

Do not bind the site to `:443` — that port is VLESS Reality.

## Cloudflare (done 2026-08-27)

Proxied A for `@` and `www` now origin **Amsterdam `107.189.22.142`** (was Frankfurt `172.86.68.87`).
Public check: `https://wingsvpn.shop/health` = 200, Happ JSON = 3 NL profiles.

Leave `ams.wingsvpn.shop` grey-cloud on AMS. Leave `cf.wingsvpn.shop` on the tunnel.
Do **not** point orange-cloud at 4VPS `:443` — that port is VLESS Reality.

SSL: keep Full (strict). Re-run if origin IPs ever change:

```
python3 infra/cloudflare/point_apex_to_ams.py --apply
```
