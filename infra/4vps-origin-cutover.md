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

## HTTPS front

`https://ams.wingsvpn.shop` (grey-cloud to AMS nginx) now proxies to 4VPS `:80`.
That host returns 200 for `/health` and `/miniapp/sub/{id}`.

`https://wingsvpn.shop` is still orange-cloud to the **dead Frankfurt origin**.
Until Cloudflare DNS is updated it will keep returning 523.

## Cloudflare (one change)

In the `wingsvpn.shop` zone, proxied A/AAAA for `@` and `www`:

- **from** Frankfurt `172.86.68.87`
- **to** AMS `107.189.22.142` (has Let's Encrypt for `wingsvpn.shop`, proxies to NL)

SSL mode: Full (strict). Do **not** point orange-cloud at 4VPS `:443` — that port
is VLESS Reality.

Optional alternative: origin `139.28.240.160` + SSL **Flexible** (HTTP `:80`).

After the A record change, Happ/2RayTun 🔄 against `wingsvpn.shop` should work.
