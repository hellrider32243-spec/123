#!/usr/bin/env python3
"""
Рассылка: новый быстрый профиль XHTTP/Турбо + напоминание про 99 ₽ (START99).

Фото: assets/xhttp_two_fast_profiles.png
Аудитория: все неблокированные пользователи бота.

  cd /opt/nordwings/app
  ./venv/bin/python broadcast_xhttp_fast_promo99_2026_08.py --dry-run
  ./venv/bin/python broadcast_xhttp_fast_promo99_2026_08.py --test-only
  ./venv/bin/python broadcast_xhttp_fast_promo99_2026_08.py --confirm-send-all
  ./venv/bin/python broadcast_xhttp_fast_promo99_2026_08.py --confirm-send-all --resume
"""
from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import sqlite3
import sys
import time
from pathlib import Path

import aiohttp

sys.path.insert(0, "/opt/nordwings/app")
os.chdir("/opt/nordwings/app")

from broadcast_common import (  # noqa: E402
    BOT_DB_PATH,
    BOT_ENV_PATH,
    MINIAPP_URL,
    BATCH_PAUSE_SEC,
    BATCH_SIZE,
    SEND_DELAY_SEC,
    Config,
    SendResult,
    db_connect,
    ensure_broadcast_log_table,
    get_all_active_user_ids,
    get_already_sent,
    log_send,
    mass_broadcast,
)

BROADCAST_TAG = "xhttp_fast_promo99_2026_08_31"
PROMO_CODE = "START99"
PROMO_PRICE = 99
BASE_PRICE = 129
TEST_ADMIN_ID = 858565509
MINIAPP_HOME_URL = MINIAPP_URL.rstrip("/") + "/"
PHOTO_PATH = "/opt/nordwings/app/assets/xhttp_two_fast_profiles.png"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-7s  %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("xhttp_fast_promo99")


CAPTION = (
    "🚀 <b>Добавили самый быстрый профиль</b>\n\n"
    "В Happ появились два режима скорости:\n\n"
    "🚀 <b>Турбо</b> — максимальная скорость и стабильность\n"
    "⚡ <b>XHTTP</b> — отличный выбор для мобильного интернета\n\n"
    "<b>Как включить:</b>\n"
    "1️⃣ Откройте <b>Happ</b>\n"
    "2️⃣ Потяните подписку вниз — обновить\n"
    "3️⃣ Выберите <b>Турбо</b> или <b>XHTTP</b>\n\n"
    "💎 <b>Напоминаем про скидку:</b>\n"
    f"<b>1 месяц — {PROMO_PRICE} ₽</b> <s>{BASE_PRICE} ₽</s>\n"
    f"Промокод <b>{PROMO_CODE}</b> применится сам — "
    "нажмите кнопку ниже.\n\n"
    "TritonVPN 💚"
)


def build_reply_markup() -> dict:
    return {
        "inline_keyboard": [
            [{"text": "💳 Купить за 99 ₽", "callback_data": "promo99_buy"}],
            [{"text": "📦 Все тарифы", "callback_data": "open_tariffs"}],
            [{"text": "📱 Mini App", "web_app": {"url": MINIAPP_HOME_URL}}],
        ]
    }


def ensure_promo_code(conn: sqlite3.Connection) -> None:
    row = conn.execute(
        "SELECT code, active FROM promo_codes WHERE code = ?",
        (PROMO_CODE,),
    ).fetchone()
    if row:
        if int(row["active"] or 0) != 1:
            conn.execute(
                "UPDATE promo_codes SET active = 1 WHERE code = ?",
                (PROMO_CODE,),
            )
            conn.commit()
            log.info("Промокод %s снова активирован", PROMO_CODE)
        else:
            log.info("Промокод %s уже активен", PROMO_CODE)
        return
    conn.execute(
        """
        INSERT INTO promo_codes (code, percent_off, max_redemptions, redemptions, active)
        VALUES (?, 23, NULL, 0, 1)
        """,
        (PROMO_CODE,),
    )
    conn.commit()
    log.info("Создан промокод %s", PROMO_CODE)


def _extract_file_id(body: dict) -> str | None:
    photos = ((body.get("result") or {}).get("photo") or [])
    if not photos:
        return None
    return photos[-1].get("file_id")


async def send_photo(
    session: aiohttp.ClientSession,
    bot_token: str,
    chat_id: int,
    *,
    photo_path: str | None = None,
    file_id: str | None = None,
    caption: str,
    reply_markup: dict | None = None,
) -> tuple[str, str | None, str | None]:
    url = f"https://api.telegram.org/bot{bot_token}/sendPhoto"
    attempts = 0
    while True:
        attempts += 1
        try:
            if file_id:
                payload = {
                    "chat_id": chat_id,
                    "photo": file_id,
                    "caption": caption[:1024],
                    "parse_mode": "HTML",
                }
                if reply_markup:
                    payload["reply_markup"] = reply_markup
                async with session.post(url, json=payload, timeout=60) as resp:
                    body = await resp.json()
            else:
                path = Path(photo_path or "")
                if not path.is_file():
                    return (SendResult.ERROR, f"photo not found: {photo_path}", None)
                data = aiohttp.FormData()
                data.add_field("chat_id", str(chat_id))
                data.add_field("caption", caption[:1024])
                data.add_field("parse_mode", "HTML")
                if reply_markup:
                    data.add_field(
                        "reply_markup",
                        json.dumps(reply_markup, ensure_ascii=False),
                    )
                with path.open("rb") as img:
                    data.add_field(
                        "photo",
                        img,
                        filename=path.name,
                        content_type="image/png",
                    )
                    async with session.post(url, data=data, timeout=60) as resp:
                        body = await resp.json()
        except asyncio.TimeoutError:
            return (SendResult.ERROR, "timeout", None)
        except Exception as e:
            return (SendResult.ERROR, f"net: {e}", None)

        if body.get("ok"):
            return (SendResult.SENT, None, _extract_file_id(body))

        code = body.get("error_code")
        descr = (body.get("description") or "").lower()
        if code == 429:
            retry_after = int((body.get("parameters") or {}).get("retry_after", 5))
            log.warning("flood wait %ds for %s (attempt %d)", retry_after, chat_id, attempts)
            if attempts > 3:
                return (SendResult.ERROR, f"flood wait exceeded ({retry_after}s)", None)
            await asyncio.sleep(retry_after + 1)
            continue
        if code == 403:
            return (SendResult.BLOCKED, descr, None)
        if code == 400 and (
            "chat not found" in descr
            or "user is deactivated" in descr
            or "peer_id_invalid" in descr
        ):
            return (SendResult.DELETED, descr, None)
        return (SendResult.ERROR, f"{code}: {descr}", None)


async def mass_broadcast_photo_cached(
    cfg: Config,
    tag: str,
    recipients: list[int],
    photo_path: str,
    caption: str,
    reply_markup: dict | None,
    skip_ids: set[int] | None = None,
    seed_chat_id: int | None = None,
) -> dict:
    if skip_ids is None:
        skip_ids = set()
    stats = {"sent": 0, "blocked": 0, "deleted": 0, "error": 0, "skipped": 0}
    total = len(recipients)
    conn = db_connect()
    ensure_broadcast_log_table(conn)
    file_id: str | None = None

    async with aiohttp.ClientSession() as session:
        if seed_chat_id and seed_chat_id not in skip_ids:
            status, err, fid = await send_photo(
                session,
                cfg.bot_token,
                seed_chat_id,
                photo_path=photo_path,
                caption=caption,
                reply_markup=reply_markup,
            )
            stats[status] = stats.get(status, 0) + 1
            log_send(conn, tag, seed_chat_id, status, err)
            if status == SendResult.SENT:
                skip_ids = set(skip_ids)
                skip_ids.add(seed_chat_id)
                if fid:
                    file_id = fid
                    log.info("photo uploaded, file_id cached")
            else:
                log.warning("seed upload failed status=%s err=%s — will upload per user", status, err)

        for i, uid in enumerate(recipients, 1):
            if uid in skip_ids:
                stats["skipped"] += 1
                continue
            status, err, fid = await send_photo(
                session,
                cfg.bot_token,
                uid,
                photo_path=None if file_id else photo_path,
                file_id=file_id,
                caption=caption,
                reply_markup=reply_markup,
            )
            if status == SendResult.SENT and fid and not file_id:
                file_id = fid
            stats[status] = stats.get(status, 0) + 1
            log_send(conn, tag, uid, status, err)
            if i % 50 == 0 or i == total:
                log.info(
                    "progress %d/%d  sent=%d blocked=%d deleted=%d error=%d skipped=%d",
                    i,
                    total,
                    stats["sent"],
                    stats["blocked"],
                    stats["deleted"],
                    stats["error"],
                    stats["skipped"],
                )
            await asyncio.sleep(SEND_DELAY_SEC)
            if i % BATCH_SIZE == 0 and i < total:
                log.info("batch pause %ds…", int(BATCH_PAUSE_SEC))
                await asyncio.sleep(BATCH_PAUSE_SEC)

    conn.close()
    return stats


async def main() -> None:
    ap = argparse.ArgumentParser(description="XHTTP/Turbo fastest profile + START99 99₽")
    mode = ap.add_mutually_exclusive_group(required=True)
    mode.add_argument("--dry-run", action="store_true")
    mode.add_argument("--test-only", action="store_true")
    mode.add_argument("--confirm-send-all", action="store_true")
    ap.add_argument("--resume", action="store_true")
    ap.add_argument("--no-countdown", action="store_true")
    args = ap.parse_args()

    cfg = Config(BOT_ENV_PATH)
    admin_id = cfg.admin_id or TEST_ADMIN_ID
    photo = Path(PHOTO_PATH)
    if not photo.is_file():
        log.error("Нет картинки: %s", PHOTO_PATH)
        sys.exit(1)

    log.info("DB:       %s", BOT_DB_PATH)
    log.info("ADMIN_ID: %s", admin_id)
    log.info("TAG:      %s", BROADCAST_TAG)
    log.info("PHOTO:    %s (%d bytes)", PHOTO_PATH, photo.stat().st_size)
    log.info("CAPTION:  %d chars", len(CAPTION))

    conn = db_connect(BOT_DB_PATH)
    ensure_broadcast_log_table(conn)
    ensure_promo_code(conn)
    all_targets = get_all_active_user_ids(conn)
    already_sent = get_already_sent(conn, BROADCAST_TAG) if args.resume else set()
    conn.close()

    markup = build_reply_markup()
    log.info("Целевая аудитория: %d", len(all_targets))
    if args.resume:
        log.info("Уже отправлено: %d", len(already_sent))
        log.info("К отправке:     %d", len(all_targets) - len(already_sent))
    log.info("─" * 60)
    for line in CAPTION.splitlines():
        log.info(line)
    log.info("─" * 60)

    if args.dry_run:
        log.info("Первые 10 user_id: %s", all_targets[:10])
        log.info("DRY RUN — отправки нет.")
        return

    if args.test_only:
        stats = await mass_broadcast_photo_cached(
            cfg,
            BROADCAST_TAG + "_test",
            [admin_id],
            PHOTO_PATH,
            CAPTION + "\n\n<i>👀 Тест — видите только вы.</i>",
            markup,
            skip_ids=set(),
        )
        log.info("TEST %s", stats)
        return

    to_send = len(all_targets) - len(already_sent)
    if not args.no_countdown:
        log.warning("Реальная отправка %d пользователям. Ctrl+C — 10 сек на отмену.", to_send)
        try:
            await asyncio.sleep(10)
        except asyncio.CancelledError:
            log.info("Отменено.")
            return

    t0 = time.time()
    stats = await mass_broadcast_photo_cached(
        cfg,
        BROADCAST_TAG,
        all_targets,
        PHOTO_PATH,
        CAPTION,
        markup,
        skip_ids=already_sent,
        seed_chat_id=admin_id,
    )
    elapsed = time.time() - t0
    log.info(
        "ИТОГ sent=%s blocked=%s deleted=%s error=%s skipped=%s time=%.0fs",
        stats["sent"],
        stats["blocked"],
        stats["deleted"],
        stats["error"],
        stats["skipped"],
        elapsed,
    )
    summary = (
        f"✅ <b>Рассылка завершена</b>\n"
        f"tag: <code>{BROADCAST_TAG}</code>\n"
        f"sent={stats['sent']} blocked={stats['blocked']} "
        f"deleted={stats['deleted']} error={stats['error']} "
        f"skipped={stats['skipped']}\n"
        f"time: {elapsed:.0f}s"
    )
    await mass_broadcast(
        cfg, BROADCAST_TAG + "_summary", [admin_id], summary, None, skip_ids=set()
    )


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        log.info("Прервано (Ctrl+C). Можно продолжить с --resume.")
