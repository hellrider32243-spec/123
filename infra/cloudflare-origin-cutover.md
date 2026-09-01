# Cloudflare origin for wingsvpn.shop

TCP `:443` on the NL VPS is Xray Reality. Do not bind nginx HTTPS there.

The NL IP `139.28.240.160` is **port-banned from RU** and Cloudflare rejects it as an HTTP origin (Error 1000 / HTTP 403: DNS points to prohibited IP). Orange-cloud **A records to this IP must not exist**.

Public HTTP (site, Mini App, Happ JSON, Platega webhook) goes through the existing tunnel `nordwings-cf` → nginx `:80`.

## DNS (keep / delete)

Delete these three records if they still point at `139.28.240.160`:

- `ams` A
- `wingsvpn.shop` A
- `www` A

Keep:

- Tunnel `cf.wingsvpn.shop` → `nordwings-cf`
- `_acme-challenge` TXT records

Do not create new A/AAAA records to `139.28.240.160`.

## Published application routes

Zero Trust → Networks → Tunnels → `nordwings-cf` → Published application routes.

Add (HTTP, `127.0.0.1:80`), leave the existing `cf.wingsvpn.shop` rules:

| Hostname            | Path | Service              |
| ------------------- | ---- | -------------------- |
| `wingsvpn.shop`     |      | `http://127.0.0.1:80` |
| `www.wingsvpn.shop` |      | `http://127.0.0.1:80` |
| `ams.wingsvpn.shop` |      | `http://127.0.0.1:80` |

Cloudflare creates the tunnel CNAMEs after the A records are gone. Adding a published hostname while an A record exists fails with “A DNS record with this name already exists.”

## SSL

SSL/TLS → Overview: **Flexible** is enough (Cloudflare HTTPS, origin HTTP `:80`). With a tunnel Cloudflare does not need to reach origin `:443`.

## After DNS is on the tunnel

Expect `https://wingsvpn.shop` 200, `/health` JSON, `/miniapp/`, Happ `/miniapp/sub/<id>`.

Telegram webhooks (live):

- main bot → `https://wingsvpn.shop/telegram-webhook`
- `@Tritonpay_bot` → `https://wingsvpn.shop/payments-bot-webhook`

User-facing `PUBLIC_BASE_URL` / Mini App / subscription URLs stay on `https://wingsvpn.shop`. Do not point Happ at sslip.io or the raw NL IP.
