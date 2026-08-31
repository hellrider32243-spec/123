#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Отдельный Telegram-бот для владельца NordWings VPN.
Показывает, когда и кто оплатил подписку (и автопродление с баланса).

Запуск:
    cd /opt/nordwings/app
    python3 admin_payments_bot.py

Переменные в .env:
    PAYMENTS_BOT_TOKEN   — токен нового бота от @BotFather
    PAYMENTS_ADMIN_IDS   — ваш Telegram ID (можно несколько через запятую)
    ADMIN_ID             — используется, если PAYMENTS_ADMIN_IDS не задан
    DB_PATH              — путь к bot.db (тот же, что у основного бота)
    PAYMENTS_POLL_INTERVAL — интервал опроса БД в секундах (по умолчанию 20)
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import sqlite3
from contextlib import closing
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Optional

from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command
from aiogram.types import Message
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
)
logger = logging.getLogger("payments_bot")

TARIFF_NAMES = {
    "1month": "1 месяц",
    "3months": "3 месяца",
    "6months": "6 месяцев",
    "1year": "1 год",
    "trial": "Пробный",
}

METHOD_LABELS = {
    "sbp": "СБП",
    "sbp_tariff": "СБП",
    "crypto": "Криптовалюта",
    "crypto_tariff": "Криптовалюта",
    "balance_tariff": "Баланс",
    "balance": "Баланс",
    "auto_renew": "Автопродление (баланс)",
    "tariff_purchase_balance": "Баланс",
}


def _parse_admin_ids() -> tuple[int, ...]:
    raw = (os.getenv("PAYMENTS_ADMIN_IDS") or os.getenv("ADMIN_ID") or "").strip()
    ids: list[int] = []
    for part in raw.replace(";", ",").split(","):
        part = part.strip()
        if not part:
            continue
        try:
            val = int(part)
            if val > 0:
                ids.append(val)
        except ValueError:
            continue
    return tuple(dict.fromkeys(ids))


@dataclass(frozen=True)
class Config:
    bot_token: str = os.getenv("PAYMENTS_BOT_TOKEN", "").strip()
    admin_ids: tuple[int, ...] = _parse_admin_ids()
    db_path: str = os.getenv("DB_PATH", "/opt/3xui-bot/bot.db")
    web_user_base: int = int(os.getenv("WEB_INTERNAL_USER_ID_BASE", "9000000000000000"))
    poll_interval: int = max(5, int(os.getenv("PAYMENTS_POLL_INTERVAL", "20")))
    state_path: Path = Path(
        os.getenv(
            "PAYMENTS_STATE_PATH",
            str(Path(__file__).resolve().parent / "admin_payments_state.json"),
        )
    )


CFG = Config()
if not CFG.bot_token:
    raise RuntimeError("PAYMENTS_BOT_TOKEN не задан — создайте бота в @BotFather и добавьте токен в .env")
if not CFG.admin_ids:
    raise RuntimeError("PAYMENTS_ADMIN_IDS или ADMIN_ID не задан — укажите свой Telegram ID")


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(CFG.db_path, timeout=10)
    conn.row_factory = sqlite3.Row
    return conn


def _load_state() -> dict[str, int]:
    if not CFG.state_path.exists():
        return {}
    try:
        data = json.loads(CFG.state_path.read_text(encoding="utf-8"))
        return {
            "last_payment_id": int(data.get("last_payment_id") or 0),
            "last_balance_history_id": int(data.get("last_balance_history_id") or 0),
            "last_trial_event_id": int(data.get("last_trial_event_id") or 0),
        }
    except Exception:
        logger.exception("Не удалось прочитать state-файл, начинаем с текущих ID")
        return {}


def _save_state(
    last_payment_id: int,
    last_balance_history_id: int,
    last_trial_event_id: int | None = None,
) -> None:
    state = _load_state()
    if last_trial_event_id is None:
        last_trial_event_id = int(state.get("last_trial_event_id") or 0)
    payload = {
        "last_payment_id": last_payment_id,
        "last_balance_history_id": last_balance_history_id,
        "last_trial_event_id": last_trial_event_id,
        "updated_at": datetime.now().isoformat(timespec="seconds"),
    }
    CFG.state_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _init_state_if_needed() -> tuple[int, int, int]:
    state = _load_state()
    last_payment_id = state.get("last_payment_id")
    last_bh_id = state.get("last_balance_history_id")
    last_trial_id = state.get("last_trial_event_id")

    with closing(_connect()) as conn:
        if last_payment_id is None:
            row = conn.execute("SELECT COALESCE(MAX(id), 0) AS m FROM payments").fetchone()
            last_payment_id = int(row["m"] if row else 0)
            logger.info("Первый запуск: отслеживаем новые оплаты с payments.id > %s", last_payment_id)
        if last_bh_id is None:
            row = conn.execute("SELECT COALESCE(MAX(id), 0) AS m FROM balance_history").fetchone()
            last_bh_id = int(row["m"] if row else 0)
            logger.info("Первый запуск: отслеживаем автопродления с balance_history.id > %s", last_bh_id)
        if last_trial_id is None:
            try:
                row = conn.execute("SELECT COALESCE(MAX(id), 0) AS m FROM trial_events").fetchone()
                last_trial_id = int(row["m"] if row else 0)
            except sqlite3.OperationalError:
                last_trial_id = 0
            logger.info("Первый запуск: отслеживаем триалы с trial_events.id > %s", last_trial_id)

    _save_state(last_payment_id, last_bh_id, last_trial_id)
    return last_payment_id, last_bh_id, last_trial_id


def _fmt_dt(value: Optional[str]) -> str:
    if not value:
        return "—"
    for fmt in (
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%dT%H:%M:%S.%f",
        "%Y-%m-%d %H:%M:%S.%f",
    ):
        try:
            return datetime.strptime(value[:26], fmt).strftime("%d.%m.%Y %H:%M")
        except ValueError:
            continue
    return str(value)[:16]


def _rub(amount: float | int) -> str:
    try:
        return f"{int(round(float(amount)))}₽"
    except Exception:
        return "0₽"


def _user_label(conn: sqlite3.Connection, user_id: int) -> str:
    if user_id >= CFG.web_user_base:
        acc_id = user_id - CFG.web_user_base
        row = conn.execute(
            "SELECT email FROM web_accounts WHERE id = ? OR vpn_user_id = ? LIMIT 1",
            (acc_id, user_id),
        ).fetchone()
        email = (row["email"] if row else "") or f"web#{acc_id}"
        return f"🌐 {email}"

    row = conn.execute(
        "SELECT username, first_name, last_name FROM users WHERE user_id = ?",
        (user_id,),
    ).fetchone()
    if not row:
        return f"ID {user_id}"

    username = (row["username"] or "").strip()
    name = " ".join(
        p for p in [(row["first_name"] or "").strip(), (row["last_name"] or "").strip()] if p
    ).strip()
    parts: list[str] = []
    if username:
        parts.append(f"@{username}")
    if name:
        parts.append(name)
    return " ".join(parts) if parts else f"ID {user_id}"


def _method_label(method: str) -> str:
    return METHOD_LABELS.get(method, method or "—")


def _tariff_label(tariff_id: Optional[str]) -> str:
    if not tariff_id:
        return "—"
    return TARIFF_NAMES.get(tariff_id, tariff_id)


TRIAL_SOURCE_LABELS = {
    "telegram_button": "Кнопка в боте",
    "broadcast": "Рассылка",
    "menu": "Меню / callback",
    "miniapp": "Mini App",
    "unknown": "—",
}


def _referral_source_label(conn: sqlite3.Connection, user_id: int) -> str:
    row = conn.execute(
        """
        SELECT r.referrer_id, u.username, u.first_name
        FROM referrals r
        LEFT JOIN users u ON u.user_id = r.referrer_id
        WHERE r.referred_id = ? LIMIT 1
        """,
        (user_id,),
    ).fetchone()
    if not row:
        return "—"
    referrer_id = int(row["referrer_id"])
    username = (row["username"] or "").strip()
    name = (row["first_name"] or "").strip()
    parts = [f"ID {referrer_id}"]
    if username:
        parts.append(f"@{username}")
    if name:
        parts.append(name)
    return " ".join(parts)


def _format_trial_event_row(conn: sqlite3.Connection, row: sqlite3.Row) -> str:
    user_id = int(row["user_id"])
    source = str(row["source"] or "unknown").strip()
    source_label = TRIAL_SOURCE_LABELS.get(source, source or "—")
    expires = _fmt_dt(str(row["expires_at"] or ""))
    when = _fmt_dt(str(row["created_at"] or ""))
    return "\n".join([
        "🎁 <b>Активирован пробный период</b>",
        "",
        f"👤 <b>Кто:</b> {_user_label(conn, user_id)}",
        f"🆔 <b>ID:</b> <code>{user_id}</code>",
        f"📍 <b>Источник:</b> {source_label}",
        f"👥 <b>Реферал:</b> {_referral_source_label(conn, user_id)}",
        f"📅 <b>До:</b> {expires}",
        f"🕐 <b>Когда:</b> {when}",
    ])


def _fetch_new_trial_events(conn: sqlite3.Connection, last_trial_event_id: int) -> list[sqlite3.Row]:
    try:
        return list(
            conn.execute(
                """
                SELECT id, user_id, source, expires_at, created_at
                FROM trial_events
                WHERE id > ? ORDER BY id ASC
                """,
                (last_trial_event_id,),
            ).fetchall()
        )
    except sqlite3.OperationalError:
        return []


def _format_subscription_payment(
    *,
    user_id: int,
    user_label: str,
    amount: float,
    method: str,
    tariff_id: Optional[str],
    devices: int,
    when: str,
    source: str = "payment",
    order_id: Optional[str] = None,
) -> str:
    title = "💰 <b>Новая оплата подписки</b>"
    if source == "auto_renew":
        title = "🔄 <b>Автопродление подписки</b>"

    lines = [
        title,
        "",
        f"👤 <b>Кто:</b> {user_label}",
        f"🆔 <b>ID:</b> <code>{user_id}</code>",
        f"📦 <b>Тариф:</b> {_tariff_label(tariff_id)}",
        f"💵 <b>Сумма:</b> {_rub(amount)}",
        f"📱 <b>Устройств:</b> {devices}",
        f"💳 <b>Способ:</b> {_method_label(method)}",
        f"🕐 <b>Когда:</b> {_fmt_dt(when)}",
    ]
    if order_id:
        lines.append(f"🧾 <b>Заказ:</b> <code>{order_id}</code>")
    return "\n".join(lines)


def _format_payment_row(conn: sqlite3.Connection, row: sqlite3.Row) -> str:
    tariff_id = _extract_tariff_id(row) or _row_val(row, "tariff_id", "plan")
    method = str(_row_val(row, "method", "payment_method", default="") or "")
    devices = int(_row_val(row, "devices_count", "devices", default=1) or 1)
    return _format_subscription_payment(
        user_id=int(row["user_id"]),
        user_label=_user_label(conn, int(row["user_id"])),
        amount=float(row["amount"] or 0),
        method=method,
        tariff_id=str(tariff_id) if tariff_id else None,
        devices=devices,
        when=str(row["completed_at"] or row["created_at"] or ""),
        source="payment",
        order_id=_row_val(row, "order_id", "payment_id"),
    )


def _format_auto_renew_row(conn: sqlite3.Connection, row: sqlite3.Row) -> Optional[str]:
    user_id = int(row["user_id"])
    amount = abs(float(row["amount"] or 0))
    desc = str(row["description"] or "")
    tariff_id = None
    for tid in TARIFF_NAMES:
        if tid in desc:
            tariff_id = tid
            break

    sub = conn.execute(
        "SELECT tariff_id, devices_count FROM subscriptions WHERE user_id = ?",
        (user_id,),
    ).fetchone()
    if sub:
        tariff_id = tariff_id or sub["tariff_id"]
        devices = int(sub["devices_count"] or 1)
    else:
        devices = 1

    return _format_subscription_payment(
        user_id=user_id,
        user_label=_user_label(conn, user_id),
        amount=amount,
        method="auto_renew",
        tariff_id=tariff_id,
        devices=devices,
        when=str(row["created_at"] or ""),
        source="auto_renew",
    )


def _payment_table_columns(conn: sqlite3.Connection) -> set[str]:
    rows = conn.execute("PRAGMA table_info(payments)").fetchall()
    return {str(r[1]) for r in rows}


def _row_val(row: sqlite3.Row, *keys: str, default: Any = None) -> Any:
    for key in keys:
        if key not in row.keys():
            continue
        val = row[key]
        if val is not None and str(val).strip() != "":
            return val
    return default


def _extract_tariff_id(row: sqlite3.Row) -> Optional[str]:
    direct = _row_val(row, "tariff_id", "plan")
    if direct:
        return str(direct)

    for field in ("payload_json", "raw_response", "raw_request"):
        raw = _row_val(row, field)
        if not raw:
            continue
        try:
            data = json.loads(raw) if isinstance(raw, str) else raw
        except Exception:
            continue
        if not isinstance(data, dict):
            continue
        for key in ("tariff_id", "plan"):
            if data.get(key):
                return str(data[key])
        meta = data.get("payload") or data.get("metadata") or data.get("extra_payload")
        if isinstance(meta, str):
            try:
                meta = json.loads(meta)
            except Exception:
                meta = None
        if isinstance(meta, dict):
            for key in ("tariff_id", "plan"):
                if meta.get(key):
                    return str(meta[key])
    return None


def _is_subscription_payment(row: sqlite3.Row) -> bool:
    if _extract_tariff_id(row):
        return True
    method = str(_row_val(row, "method", "payment_method", default="") or "").lower()
    return "tariff" in method or method in {"tariff_purchase_balance"}


def _subscription_payments_sql(columns: set[str]) -> str:
    method_expr = "COALESCE(method, payment_method, '')" if {"method", "payment_method"} & columns else (
        "method" if "method" in columns else "payment_method" if "payment_method" in columns else "''"
    )
    tariff_parts: list[str] = []
    if "tariff_id" in columns:
        tariff_parts.append("NULLIF(tariff_id, '')")
    if "plan" in columns:
        tariff_parts.append("NULLIF(plan, '')")
    tariff_expr = f"COALESCE({', '.join(tariff_parts)})" if tariff_parts else "NULL"

    devices_expr = (
        "COALESCE(devices_count, devices, 1)"
        if {"devices_count", "devices"} & columns
        else ("devices_count" if "devices_count" in columns else "devices" if "devices" in columns else "1")
    )

    extra_cols = []
    for col in ("plan", "payment_method", "devices", "payload_json", "raw_response", "raw_request"):
        if col in columns:
            extra_cols.append(col)

    select_extra = (", " + ", ".join(extra_cols)) if extra_cols else ""

    subscription_filter = f"({tariff_expr} IS NOT NULL"
    subscription_filter += f" OR {method_expr} LIKE '%tariff%'"
    subscription_filter += " OR method = 'tariff_purchase_balance'" if "method" in columns else ""
    subscription_filter += ")"

    return f"""
        SELECT id, user_id, amount,
               {method_expr} AS method,
               {tariff_expr} AS tariff_id,
               {devices_expr} AS devices_count,
               order_id, payment_id, created_at, completed_at,
               status{select_extra}
        FROM payments
        WHERE status = 'paid'
          AND {subscription_filter}
    """


def _fetch_subscription_payments(limit: int, since: Optional[datetime] = None) -> list[sqlite3.Row]:
    with closing(_connect()) as conn:
        cols = _payment_table_columns(conn)
        if not cols:
            return []
        sql = _subscription_payments_sql(cols)
        params: list[Any] = []
        if since:
            sql += " AND COALESCE(completed_at, created_at) >= ?"
            params.append(since.strftime("%Y-%m-%d %H:%M:%S"))
        sql += " ORDER BY id DESC LIMIT ?"
        params.append(limit)
        rows = list(conn.execute(sql, params).fetchall())

    normalized: list[sqlite3.Row] = []
    for row in rows:
        if not _is_subscription_payment(row):
            continue
        normalized.append(row)
    return normalized


def _fetch_new_subscription_payments(conn: sqlite3.Connection, last_payment_id: int) -> list[sqlite3.Row]:
    cols = _payment_table_columns(conn)
    if not cols:
        return []
    sql = _subscription_payments_sql(cols) + " AND id > ? ORDER BY id ASC"
    rows = list(conn.execute(sql, (last_payment_id,)).fetchall())
    return [row for row in rows if _is_subscription_payment(row)]


def _stats_text() -> str:
    now = datetime.now()
    day_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    week_start = day_start - timedelta(days=day_start.weekday())
    month_start = day_start.replace(day=1)

    def block(label: str, start: datetime) -> tuple[int, float]:
        rows = _fetch_subscription_payments(limit=10_000, since=start)
        total = sum(float(r["amount"] or 0) for r in rows)
        return len(rows), total

    today_n, today_sum = block("сегодня", day_start)
    week_n, week_sum = block("неделя", week_start)
    month_n, month_sum = block("месяц", month_start)

    return (
        "📊 <b>Статистика оплат подписок</b>\n\n"
        f"Сегодня: <b>{today_n}</b> на <b>{_rub(today_sum)}</b>\n"
        f"С начала недели: <b>{week_n}</b> на <b>{_rub(week_sum)}</b>\n"
        f"С начала месяца: <b>{month_n}</b> на <b>{_rub(month_sum)}</b>"
    )


bot = Bot(token=CFG.bot_token)
dp = Dispatcher()


def _is_admin(user_id: int) -> bool:
    return user_id in CFG.admin_ids


async def _notify_admins(text: str) -> None:
    for admin_id in CFG.admin_ids:
        try:
            await bot.send_message(admin_id, text, parse_mode="HTML")
        except Exception:
            logger.exception("Не удалось отправить сообщение admin_id=%s", admin_id)


@dp.message(Command("start", "help"))
async def cmd_start(message: Message) -> None:
    if not message.from_user or not _is_admin(message.from_user.id):
        await message.answer("⛔ Доступ только для администратора.")
        return
    await message.answer(
        "👋 <b>Бот уведомлений об оплатах NordWings</b>\n\n"
        "Я присылаю сообщение, когда кто-то оплатил подписку или активировал пробный период "
        "(СБП, крипта, баланс, автопродление).\n\n"
        "<b>Команды:</b>\n"
        "/today — оплаты за сегодня\n"
        "/last — последние 10 оплат\n"
        "/last 20 — последние N оплат\n"
        "/stats — статистика за день / неделю / месяц\n"
        "/pending — незакрытые счета (СБП/крипта)\n"
        "/catchup — прислать уведомления за последние 24 ч (если пропустил)\n"
        "/debug — диагностика подключения к БД",
        parse_mode="HTML",
    )


@dp.message(Command("today"))
async def cmd_today(message: Message) -> None:
    if not message.from_user or not _is_admin(message.from_user.id):
        return
    day_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    rows = _fetch_subscription_payments(limit=100, since=day_start)
    if not rows:
        await message.answer("Сегодня оплат подписок пока не было.")
        return
    with closing(_connect()) as conn:
        chunks = [_format_payment_row(conn, row) for row in reversed(rows)]
    await message.answer(
        f"📅 <b>Оплаты за сегодня ({len(rows)}):</b>\n\n" + "\n\n—\n\n".join(chunks),
        parse_mode="HTML",
    )


@dp.message(Command("last"))
async def cmd_last(message: Message) -> None:
    if not message.from_user or not _is_admin(message.from_user.id):
        return
    limit = 10
    if message.text:
        parts = message.text.split()
        if len(parts) >= 2 and parts[1].isdigit():
            limit = min(max(int(parts[1]), 1), 50)
    rows = _fetch_subscription_payments(limit=limit)
    if not rows:
        await message.answer("Оплат подписок пока нет.")
        return
    with closing(_connect()) as conn:
        chunks = [_format_payment_row(conn, row) for row in reversed(rows)]
    await message.answer(
        f"🧾 <b>Последние {len(rows)} оплат:</b>\n\n" + "\n\n—\n\n".join(chunks),
        parse_mode="HTML",
    )


@dp.message(Command("stats"))
async def cmd_stats(message: Message) -> None:
    if not message.from_user or not _is_admin(message.from_user.id):
        return
    await message.answer(_stats_text(), parse_mode="HTML")


@dp.message(Command("pending"))
async def cmd_pending(message: Message) -> None:
    if not message.from_user or not _is_admin(message.from_user.id):
        return
    with closing(_connect()) as conn:
        rows = list(
            conn.execute(
                """
                SELECT id, user_id, amount, status, created_at,
                       COALESCE(method, '') AS method,
                       COALESCE(tariff_id, '') AS tariff_id,
                       COALESCE(order_id, payment_id, '') AS order_id
                FROM payments
                WHERE status = 'pending'
                ORDER BY id DESC
                LIMIT 20
                """
            ).fetchall()
        )
        crypto = list(
            conn.execute(
                "SELECT invoice_id, user_id, amount, status, created_at FROM crypto_payments WHERE status = 'pending' ORDER BY id DESC LIMIT 10"
            ).fetchall()
        )
    if not rows and not crypto:
        await message.answer("Висящих pending-оплат нет.")
        return
    lines = [f"⏳ <b>Pending в payments: {len(rows)}</b>"]
    for r in rows:
        lines.append(
            f"#{r['id']} uid=<code>{r['user_id']}</code> {_rub(r['amount'] or 0)} "
            f"{r['method'] or '—'} {r['tariff_id'] or '—'} {_fmt_dt(r['created_at'])}"
        )
    if crypto:
        lines.append("")
        lines.append(f"⏳ <b>Pending crypto: {len(crypto)}</b>")
        for r in crypto:
            lines.append(
                f"uid=<code>{r['user_id']}</code> {_rub(r['amount'] or 0)} {_fmt_dt(r['created_at'])}"
            )
    await message.answer("\n".join(lines), parse_mode="HTML")


@dp.message(Command("debug"))
async def cmd_debug(message: Message) -> None:
    if not message.from_user or not _is_admin(message.from_user.id):
        return

    state = _load_state()
    db_exists = Path(CFG.db_path).exists()
    lines = [
        "🔧 <b>Диагностика</b>",
        "",
        f"📁 DB: <code>{CFG.db_path}</code>",
        f"{'✅ файл есть' if db_exists else '❌ файл не найден'}",
        f"📌 state: last_payment_id={state.get('last_payment_id', '—')}, "
        f"last_bh_id={state.get('last_balance_history_id', '—')}",
    ]

    if db_exists:
        try:
            with closing(_connect()) as conn:
                cols = sorted(_payment_table_columns(conn))
                total = conn.execute("SELECT COUNT(*) AS c FROM payments").fetchone()["c"]
                paid = conn.execute("SELECT COUNT(*) AS c FROM payments WHERE status='paid'").fetchone()["c"]
                recent = conn.execute(
                    "SELECT * FROM payments ORDER BY id DESC LIMIT 5"
                ).fetchall()
            lines.append(f"📊 Всего записей: {total}, оплачено: {paid}")
            lines.append(f"🧱 Колонки: {', '.join(cols[:12])}{'…' if len(cols) > 12 else ''}")
            sub_count = len(_fetch_subscription_payments(limit=100))
            lines.append(f"📦 Оплат подписок (всего в выборке): {sub_count}")
            if recent:
                lines.append("")
                lines.append("<b>Последние 5 платежей:</b>")
                for r in recent:
                    tariff = _extract_tariff_id(r) or "—"
                    method = _row_val(r, "method", "payment_method", default="—")
                    when = _row_val(r, "completed_at", "created_at", default="—")
                    lines.append(
                        f"#{r['id']} uid={r['user_id']} {r['amount']}₽ "
                        f"{r['status']} тариф={tariff} {method} {when}"
                    )
        except Exception as exc:
            lines.append(f"❌ Ошибка БД: <code>{exc}</code>")

    await message.answer("\n".join(lines), parse_mode="HTML")


@dp.message(Command("catchup"))
async def cmd_catchup(message: Message) -> None:
    """Отправить уведомления по оплатам за 24 ч, которые могли быть пропущены."""
    if not message.from_user or not _is_admin(message.from_user.id):
        return

    since = datetime.now() - timedelta(hours=24)
    rows = _fetch_subscription_payments(limit=100, since=since)
    if not rows:
        await message.answer(
            "За последние 24 часа оплат подписок в БД не найдено.\n"
            "Отправьте /debug — посмотрим, что в базе."
        )
        return

    sent = 0
    max_id = _load_state().get("last_payment_id", 0)
    with closing(_connect()) as conn:
        for row in reversed(rows):
            text = _format_payment_row(conn, row)
            await _notify_admins(text)
            sent += 1
            max_id = max(max_id, int(row["id"]))

    state = _load_state()
    _save_state(
        max_id,
        int(state.get("last_balance_history_id") or 0),
        int(state.get("last_trial_event_id") or 0),
    )
    await message.answer(f"✅ Отправлено уведомлений: {sent} (за последние 24 ч).")


@dp.message(F.text)
async def deny_others(message: Message) -> None:
    if message.from_user and not _is_admin(message.from_user.id):
        await message.answer("⛔ Доступ только для администратора.")


async def watch_payments_loop() -> None:
    last_payment_id, last_bh_id, last_trial_id = _init_state_if_needed()
    logger.info(
        "Watcher started: payments.id > %s, balance_history.id > %s, trial_events.id > %s, interval=%ss",
        last_payment_id,
        last_bh_id,
        last_trial_id,
        CFG.poll_interval,
    )

    while True:
        try:
            with closing(_connect()) as conn:
                payment_rows = _fetch_new_subscription_payments(conn, last_payment_id)

                renew_rows = []
                try:
                    renew_rows = conn.execute(
                        """
                        SELECT id, user_id, amount, operation_type, description, created_at
                        FROM balance_history
                        WHERE id > ?
                          AND operation_type = 'auto_renew'
                        ORDER BY id ASC
                        """,
                        (last_bh_id,),
                    ).fetchall()
                except sqlite3.OperationalError:
                    pass

                trial_rows = _fetch_new_trial_events(conn, last_trial_id)

            for row in payment_rows:
                with closing(_connect()) as conn:
                    text = _format_payment_row(conn, row)
                await _notify_admins(text)
                last_payment_id = int(row["id"])
                _save_state(last_payment_id, last_bh_id, last_trial_id)
                logger.info("Уведомление об оплате payments.id=%s user_id=%s", row["id"], row["user_id"])

            for row in renew_rows:
                with closing(_connect()) as conn:
                    text = _format_auto_renew_row(conn, row)
                if text:
                    await _notify_admins(text)
                last_bh_id = int(row["id"])
                _save_state(last_payment_id, last_bh_id, last_trial_id)
                logger.info("Уведомление об автопродлении balance_history.id=%s", row["id"])

            for row in trial_rows:
                with closing(_connect()) as conn:
                    text_msg = _format_trial_event_row(conn, row)
                await _notify_admins(text_msg)
                last_trial_id = int(row["id"])
                _save_state(last_payment_id, last_bh_id, last_trial_id)
                logger.info("Уведомление о триале trial_events.id=%s user_id=%s", row["id"], row["user_id"])

        except Exception:
            logger.exception("Ошибка в цикле опроса БД")

        await asyncio.sleep(CFG.poll_interval)


async def main() -> None:
    if not Path(CFG.db_path).exists():
        logger.warning("Файл БД не найден: %s — проверьте DB_PATH", CFG.db_path)

    asyncio.create_task(watch_payments_loop())
    logger.info("Admin payments bot started for admin_ids=%s", CFG.admin_ids)
    await dp.start_polling(bot)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Admin payments bot stopped")
