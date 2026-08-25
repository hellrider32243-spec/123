#!/usr/bin/env python3
"""Рассылка: обновление NL-сервера + фикс Telegram/Happ + акция 99 ₽.

  cd /opt/nordwings/app
  ./venv/bin/python broadcast_nl_fix_promo99_2026_08_25.py --dry-run
  ./venv/bin/python broadcast_nl_fix_promo99_2026_08_25.py --test-only
  ./venv/bin/python broadcast_nl_fix_promo99_2026_08_25.py --send
  ./venv/bin/python broadcast_nl_fix_promo99_2026_08_25.py --send --resume
"""
from __future__ import annotations

import argparse
import asyncio

from broadcast_common import (
    Config,
    MINIAPP_URL,
    db_connect,
    ensure_broadcast_log_table,
    get_all_active_user_ids,
    get_already_sent,
    mass_broadcast,
    setup_logging,
)

log = setup_logging("nl_fix_99")
BROADCAST_TAG = "nl_fix_promo99_2026_08_25"

TEXT = (
    "🔄 <b>Обновление TritonVPN</b>\n"
    "\n"
    "Починили подключение и ускорили работу:\n"
    "• новый сервер в Нидерландах\n"
    "• 3 профиля: <b>Турбо</b>, <b>Нидерланды</b>, <b>Hysteria</b>\n"
    "• <b>Турбо</b> — самый быстрый, стоит первым\n"
    "• исправили Telegram и ошибку Happ\n"
    "\n"
    "<b>Что сделать:</b>\n"
    "Откройте Happ → подписка TritonVPN → потяните список вниз.\n"
    "Старые серверы лучше удалить и оставить новые три.\n"
    "\n"
    "🔥 <b>Напоминаем про акцию</b>\n"
    "<blockquote>"
    "📅 1 месяц\n"
    "💰 <s>129 ₽</s> → <b>99 ₽</b>\n"
    "⚡ Турбо · Нидерланды · Hysteria"
    "</blockquote>\n"
    "\n"
    "Полный месяц по спеццене — успейте взять 👇"
)


def build_markup() -> dict:
    return {
        "inline_keyboard": [
            [{"text": "🔥 Купить за 99 ₽", "callback_data": "promo99_buy"}],
            [{"text": "📦 Все тарифы", "callback_data": "open_tariffs"}],
            [{"text": "📲 Открыть TritonVPN", "web_app": {"url": MINIAPP_URL}}],
        ]
    }


async def main() -> None:
    ap = argparse.ArgumentParser()
    mode = ap.add_mutually_exclusive_group(required=True)
    mode.add_argument("--dry-run", action="store_true")
    mode.add_argument("--test-only", action="store_true")
    mode.add_argument("--send", action="store_true")
    ap.add_argument("--resume", action="store_true")
    args = ap.parse_args()

    cfg = Config()
    conn = db_connect()
    ensure_broadcast_log_table(conn)

    users = get_all_active_user_ids(conn)
    text = TEXT
    markup = build_markup()

    if args.test_only:
        users = [cfg.admin_id] if cfg.admin_id else users[:1]
        log.info("TEST-ONLY → %s", users)

    if args.resume:
        already = get_already_sent(conn, BROADCAST_TAG)
        users = [u for u in users if u not in already]
        log.info("resume: skip already sent, left=%s", len(users))

    log.info("Получателей: %d (tag=%s)", len(users), BROADCAST_TAG)

    if args.dry_run:
        print(f"DRY-RUN: {len(users)} пользователей")
        print("--- текст ---")
        print(text.replace("<b>", "").replace("</b>", "").replace("<blockquote>", "").replace("</blockquote>", ""))
        return

    stats = await mass_broadcast(
        cfg,
        BROADCAST_TAG,
        users,
        text,
        markup,
        skip_ids=set(),
    )
    log.info("Итог: %s", stats)
    print("DONE", stats, flush=True)


if __name__ == "__main__":
    asyncio.run(main())
