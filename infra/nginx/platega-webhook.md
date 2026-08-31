# Payment webhooks and admin bot

## Admin bot

`@Tritonpay_bot` (`app/admin_payments_bot.py`) polls `bot.db` and DMs `PAYMENTS_ADMIN_IDS` when a subscription is paid.

systemd: `infra/systemd/nordwings-payments-bot.service`

Commands: `/today` `/last` `/stats` `/pending` `/catchup` `/debug`

## Fulfillment

- Public Platega URL: `POST https://wingsvpn.shop/api/platega-webhook` → nginx `/api/` → web `:8001`
- Bot also accepts `POST /platega-webhook` and `POST /api/platega-webhook` on `:8081`
- `auto_check_payments` in `bot_api.py` polls **CryptoBot and Platega** pending rows every ~90s and fulfills `CONFIRMED` / `PAID` (covers missed webhooks after cutover)
- Paid tariff orders are marked `done`. Stale pending (>48h, not confirmed) become `expired`.
