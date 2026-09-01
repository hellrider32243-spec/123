# Cloudflare origin for wingsvpn.shop

TCP `:443` on the NL VPS is Xray Reality. The public site must stay on **HTTP origin port 80**.

1. Cloudflare → DNS
   - `wingsvpn.shop` A → `139.28.240.160` (Proxied / orange cloud)
   - `www` CNAME or A to the same
   - `ams.wingsvpn.shop` A → `139.28.240.160` (DNS only or proxied)
2. SSL/TLS → Overview: **Flexible** (Cloudflare HTTPS, origin HTTP :80)
3. SSL/TLS → Edge Certificates: HTTPS stays on
4. After this, `https://wingsvpn.shop` and Happ `https://wingsvpn.shop/miniapp/sub/<id>` work again

Until that change, temporary HTTPS is `https://wingsvpn.139.28.240.160.sslip.io:88/` (Telegram webhook port). Port 2087 also serves the same site.
