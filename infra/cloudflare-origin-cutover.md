# Cloudflare origin for wingsvpn.shop

TCP `:443` on the NL VPS is Xray Reality. The public site must stay on **HTTP origin port 80**.

1. Cloudflare → DNS
   - `wingsvpn.shop` A → `139.28.240.160` (Proxied / orange cloud)
   - `www` CNAME or A to the same
   - `ams.wingsvpn.shop` A → `139.28.240.160` (DNS only or proxied)
2. SSL/TLS → Overview: **Flexible** (Cloudflare HTTPS, origin HTTP :80)
3. SSL/TLS → Edge Certificates: HTTPS stays on
4. After this, `https://wingsvpn.shop` and Happ `https://wingsvpn.shop/miniapp/sub/<id>` work again

The NL IP is port-banned from RU, so users must not fetch the site or Happ JSON from `139.28.240.160` / sslip.io. Cloudflare anycast (`wingsvpn.shop`) is the only public HTTP path.

Telegram webhooks can stay on sslip.io:88 (Telegram DCs are not RU-blocked). After this cutover, switch them to `https://wingsvpn.shop/telegram-webhook`.
