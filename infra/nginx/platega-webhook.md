# Platega / SBP webhook routing (main VPS)

## Symptom

User pays via SBP in the Telegram bot → Platega status `CONFIRMED`, but local
`payments.status` stays `pending` and no key / subscription is issued until a
manual fulfill.

Example (2026-08-06): `@opasnoPRo` (`442893629`), order
`promo99_1month_442893629_1786045522`, payment
`f1e3707a-1c2a-4dbf-a39a-df9fa6a01869`.

## Cause

1. Bot creates the Platega invoice and writes `payments` into the **Frankfurt**
   DB (`/opt/3xui-bot/bot.db` on `172.86.68.87`).
2. Public `https://wingsvpn.shop/api/platega-webhook` was proxied to the
   **Amsterdam** web API (`107.189.22.142:8001`), which uses a **stale local
   copy** of the same DB path.
3. AMS logged `Payment not found for order_id=...` and skipped fulfillment.
4. Bot `auto_check_payments()` only polled **CryptoBot** invoices, not pending
   SBP rows — so there was no backup path.

## Fix (applied on main VPS)

### nginx — fulfill on the bot (live DB)

In `/etc/nginx/sites-enabled/wingsvpn.shop`:

```nginx
location = /api/platega-webhook {
    proxy_pass http://127.0.0.1:8081/platega-webhook;
    proxy_http_version 1.1;
    proxy_set_header Host wingsvpn.shop;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto https;
    proxy_set_header X-Secret $http_x_secret;
    proxy_set_header X-MerchantId $http_x_merchantid;
}

location = /crypto-webhook {
    proxy_pass http://127.0.0.1:8081/crypto-webhook;
    proxy_http_version 1.1;
    proxy_set_header Host wingsvpn.shop;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto https;
}
```

`nginx -t && systemctl reload nginx`

### bot — SBP poll backup

In `/opt/nordwings/app/bot_api.py`:

- Extract `fulfill_platega_payment_data(data)` from the webhook handler.
- Extend `auto_check_payments()` to poll pending SBP `payments` via
  `platega_client.get_payment_status` and fulfill on `CONFIRMED`.

### watchdog

`vpn-watchdog.service` was falsely failing on Reality SNI (`www.apple.com` vs
legacy `hh.ru`) and restarting `nordwings-bot` every ~50s around payment time.
Service disabled; SNI allowlist patched in `/opt/nordwings/bin/vpn_watchdog.py`.

## Verify

```bash
curl -s -o /dev/null -w "%{http_code}\n" -X POST https://wingsvpn.shop/api/platega-webhook \
  -H "Content-Type: application/json" \
  -d '{"id":"probe","status":"PENDING","amount":1,"payload":"{}"}'
# expect 200 + bot log "PLATEGA WEBHOOK RAW"
```
