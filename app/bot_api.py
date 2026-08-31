#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import asyncio
import base64
import hashlib
import hmac
import html as html_lib
import json
import logging
import os
import random
import secrets
import sqlite3
import string
import time
import urllib.parse
import uuid
from contextlib import closing
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Optional, Union

from dotenv import load_dotenv

load_dotenv()

import requests
import urllib3
from aiohttp import ClientSession, web, ClientTimeout
from web_auth_aiohttp import setup_web_auth_routes
import wheel_fortune as wheel
from trial_promo_notify import schedule_trial_promo_welcome
from app_import_links import (
    build_app_deep_link,
    build_happ_deep_link,
    build_incy_deep_link,
    app_import_redirect_html,
    subscription_import_https_url,
    INCY_IOS_URL,
    INCY_ANDROID_URL,
    HAPP_IOS_URL,
    HAPP_ANDROID_URL,
)
from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import (
    FSInputFile,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
    WebAppInfo,
)
import referral_contest_2026 as ref_contest
urllib3.disable_warnings()
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s"
)
logger = logging.getLogger("triton")


# =============================================================================
# CONFIG
# =============================================================================

@dataclass(frozen=True)
class Config:
    bot_token: str            = os.getenv("BOT_TOKEN", "")
    bot_username: str         = os.getenv("BOT_USERNAME", "tritonvpn_bot")
    support_username: str     = os.getenv("SUPPORT_USERNAME", "Tritonhelp")
    admin_id: int             = int(os.getenv("ADMIN_ID", "0"))
    db_path: str              = os.getenv("DB_PATH", "/opt/3xui-bot/bot.db")
    webhook_port: int         = int(os.getenv("WEBHOOK_PORT", "8081"))
    server_ip: str            = os.getenv("SERVER_IP", "127.0.0.1")
    server_port: str          = os.getenv("SERVER_PORT", "443")
    sni: str                  = os.getenv("SNI", "deepl.com")
    base_path: str            = os.getenv("BASE_PATH", "/Mqrn6Qz0KCSAP1pUZD/")
    base_url: str             = os.getenv("BASE_URL", "https://127.0.0.1:18443/Mqrn6QzOKCSAP1pUZD")
    # XUI_API_URL: адрес 3x-ui для API-запросов. Если не задан — берётся из BASE_URL.
    # Пример для HTTP: XUI_API_URL=http://127.0.0.1:2053
    xui_api_url: str          = os.getenv("XUI_API_URL", "")
    xui_db_path: str          = os.getenv("XUI_DB_PATH", "/etc/x-ui/x-ui.db")
    inbound_id: int           = int(os.getenv("INBOUND_ID", "13"))
    xui_username: str         = os.getenv("XUI_USERNAME", "")
    xui_password: str         = os.getenv("XUI_PASSWORD", "")
    crypto_token: str         = os.getenv("CRYPTO_TOKEN", "")
    crypto_api_url: str       = os.getenv("CRYPTO_API_URL", "https://pay.crypt.bot/api")
    platega_merchant_id: str  = os.getenv("PLATEGA_MERCHANT_ID", "")
    platega_api_key: str      = os.getenv("PLATEGA_API_KEY", "")
    platega_api_url: str      = os.getenv("PLATEGA_API_URL", "https://app.platega.io")
    mini_app_url: str         = os.getenv("MINI_APP_URL", "https://ams.wingsvpn.shop/miniapp/")
    public_base_url: str      = os.getenv("PUBLIC_BASE_URL", "https://ams.wingsvpn.shop")
    trial_days: int           = int(os.getenv("TRIAL_DAYS", "3"))
    referral_bonus: int       = int(os.getenv("REFERRAL_BONUS", "30"))
    api_timeout: int          = int(os.getenv("API_TIMEOUT", "20"))
    jwt_secret: str           = os.getenv("JWT_SECRET", "change_me")
    public_vless_host: str    = os.getenv("PUBLIC_VLESS_HOST", "139.28.240.160")
    public_vless_port: int    = int(os.getenv("PUBLIC_VLESS_PORT", "443"))
    public_ws_path: str       = os.getenv("PUBLIC_WS_PATH", "/ws")
    subscription_base_url: str = os.getenv("SUBSCRIPTION_BASE_URL", "https://ams.wingsvpn.shop/miniapp/sub")
    key_issuer_token: str     = os.getenv("KEY_ISSUER_TOKEN", "").strip()
    reality_pbk: str          = os.getenv("REALITY_PBK", "")
    reality_sid: str          = os.getenv("REALITY_SID", "")
    reality_fp: str           = os.getenv("REALITY_FP", os.getenv("GRPC_REALITY_FP", "safari")).strip()
    vless_flow: str           = os.getenv("VLESS_FLOW", "").strip()
    # Happ: авто-фрагментация в подписке (обход DPI без ручных настроек)
    happ_fragment: str        = os.getenv("HAPP_FRAGMENT", "80-250,10-100,tlshello").strip()
    subscription_format: str  = os.getenv("SUBSCRIPTION_FORMAT", "json").strip().lower()
    grpc_inbound_port: int    = int(os.getenv("GRPC_INBOUND_PORT", "2053"))
    grpc_service_name: str    = os.getenv("GRPC_SERVICE_NAME", "log").strip()
    tcp_inbound_id: int       = int(os.getenv("TCP_INBOUND_ID", "0"))
    tcp_inbound_port: int     = int(os.getenv("TCP_INBOUND_PORT", "2053"))
    xhttp_inbound_id: int     = int(os.getenv("XHTTP_INBOUND_ID", "0"))
    vpn_profile_name: str     = os.getenv("VPN_PROFILE_NAME", "TritonVPN").strip()
    vpn_max_devices: int      = int(os.getenv("VPN_MAX_DEVICES", "2"))
    vpn_device_limit_ip: int  = int(os.getenv("VPN_DEVICE_LIMIT_IP", os.getenv("VPN_MAX_DEVICES", "2")))
    vpn_device_limit_text: str = os.getenv(
        "VPN_DEVICE_LIMIT_TEXT",
        "📱 До 2 устройств одновременно на одну подписку",
    ).strip()


CFG = Config()
if not CFG.bot_token:
    raise RuntimeError("BOT_TOKEN не задан")

# Сессии email-кабинета (см. web_auth_aiohttp); не путать с web_sessions (Mini App).
WEB_AUTH_SESSIONS_TABLE = "web_auth_sessions"
# Синтетический users.user_id для веб-аккаунтов без Telegram (BASE + web_accounts.id).
WEB_INTERNAL_USER_ID_BASE = int(os.getenv("WEB_INTERNAL_USER_ID_BASE", "9000000000000000"))

TARIFFS = {
    "1month":  {"name": "1 месяц",   "days": 30,  "price": 129,  "emoji": "📅"},
    "3months": {"name": "3 месяца",  "days": 90,  "price": 348,  "emoji": "🗓️"},
    "6months": {"name": "6 месяцев", "days": 180, "price": 620,  "emoji": "🚀"},
    "1year":   {"name": "1 год",     "days": 365, "price": 1085, "emoji": "💎"},
    "trial":   {"name": "Пробный",   "days": int(os.getenv("TRIAL_DAYS", "3")), "price": 0, "emoji": "🎁"},
}


# =============================================================================
# UTILS
# =============================================================================

def rub(amount: float | int) -> str:
    try:
        return f"{int(round(float(amount)))}₽"
    except Exception:
        return "0₽"


def now() -> datetime:
    return datetime.now()


def generate_ref_code(length: int = 8) -> str:
    return "".join(random.choices(string.ascii_uppercase + string.digits, k=length))


def safe_name(user: types.User) -> str:
    return user.username or user.first_name or "друг"


_reality_cache: dict[str, Any] = {"ts": 0.0, "params": None}
REALITY_CACHE_TTL_SEC = 300


def _reality_from_inbound(inbound: dict) -> dict:
    raw_stream = inbound.get("streamSettings") or "{}"
    stream = json.loads(raw_stream) if isinstance(raw_stream, str) else raw_stream
    rs = stream.get("realitySettings") or {}
    settings = rs.get("settings") or {}
    dest = str(rs.get("dest") or "")
    sni = ""
    if dest and ":" in dest:
        sni = dest.split(":")[0]
    elif rs.get("serverNames"):
        sni = rs["serverNames"][0]
    short_ids = rs.get("shortIds") or []
    spx = settings.get("spiderX") or settings.get("spiderx") or "/"
    if spx == "":
        spx = "/"
    elif spx and not str(spx).startswith("/"):
        spx = f"/{spx}"
    sid = ""
    for candidate in short_ids:
        if str(candidate).strip():
            sid = str(candidate).strip()
            break
    if not sid:
        sid = CFG.reality_sid or ""
    grpc = stream.get("grpcSettings") or {}
    return {
        "port": int(inbound.get("port") or CFG.public_vless_port or 8443),
        "sni": sni or CFG.sni or "deepl.com",
        "pbk": settings.get("publicKey") or CFG.reality_pbk or "",
        "sid": sid,
        "spx": spx or "/",
        "network": stream.get("network") or "tcp",
        "serviceName": (grpc.get("serviceName") or CFG.grpc_service_name or "ws"),
    }


def get_reality_params(force: bool = False) -> dict:
    now_ts = time.time()
    if (
        not force
        and _reality_cache["params"]
        and now_ts - float(_reality_cache["ts"] or 0) < REALITY_CACHE_TTL_SEC
    ):
        return _reality_cache["params"]
    inbound = xui._get_inbound()
    if inbound:
        params = _reality_from_inbound(inbound)
    else:
        params = {
            "port": int(CFG.public_vless_port or 8443),
            "sni": CFG.sni or "deepl.com",
            "pbk": CFG.reality_pbk or "",
            "sid": CFG.reality_sid or "",
            "spx": "/",
        }
    _reality_cache["ts"] = now_ts
    _reality_cache["params"] = params
    return params


def encode_reality_spx(spx: str) -> str:
    path = spx if spx.startswith("/") else f"/{spx}"
    return urllib.parse.quote(path, safe="")


def make_vless_link(client_id: str, email: str) -> str:
    host = CFG.public_vless_host
    reality = get_reality_params()
    port = int(reality.get("port") or CFG.public_vless_port or 8443)
    sni = reality.get("sni") or CFG.sni or "deepl.com"
    pbk = reality.get("pbk") or CFG.reality_pbk or ""
    sid = reality.get("sid") or CFG.reality_sid or ""
    spx = encode_reality_spx(reality.get("spx") or "/")
    network = (reality.get("network") or "tcp").lower()
    fp = CFG.reality_fp or "safari"
    if network == "grpc":
        svc = urllib.parse.quote(reality.get("serviceName") or CFG.grpc_service_name or "ws", safe="")
        link = (
            f"vless://{client_id}@{host}:{port}"
            f"?type=grpc"
            f"&security=reality"
            f"&sni={sni}"
            f"&fp={fp}"
            f"&pbk={pbk}"
            f"&sid={sid}"
            f"&serviceName={svc}"
            f"&encryption=none"
        )
    else:
        link = (
            f"vless://{client_id}@{host}:{port}"
            f"?type=tcp"
            f"&security=reality"
            f"&sni={sni}"
            f"&fp={fp}"
            f"&pbk={pbk}"
            f"&sid={sid}"
            f"&spx={spx}"
            f"&encryption=none"
        )
        if CFG.vless_flow:
            link += f"&flow={urllib.parse.quote(CFG.vless_flow, safe='')}"
    link += f"#{urllib.parse.quote(email)}"
    return link


def pretty_subscription_link(user_id: int) -> str:
    sub_base = (CFG.subscription_base_url or "").rstrip("/")
    if sub_base:
        return f"{sub_base}/{user_id}"
    return f"{CFG.public_base_url.rstrip('/')}/miniapp/sub/{user_id}"


def happ_fragment_parts() -> tuple[str, str, str]:
    parts = (CFG.happ_fragment or "80-250,10-100,tlshello").split(",")
    return (
        parts[0] if len(parts) > 0 else "80-250",
        parts[1] if len(parts) > 1 else "10-100",
        parts[2] if len(parts) > 2 else "tlshello",
    )


def append_happ_fragment_to_vless(link: str) -> str:
    frag = CFG.happ_fragment
    if not link or not frag or "fragment=" in link:
        return link
    if "#" in link:
        main, tag = link.rsplit("#", 1)
        sep = "&" if "?" in main else "?"
        return f"{main}{sep}fragment={frag}#{tag}"
    sep = "&" if "?" in link else "?"
    return f"{link}{sep}fragment={frag}"


def vpn_device_limit_ip() -> int:
    return max(1, int(CFG.vpn_device_limit_ip or CFG.vpn_max_devices or 2))


def apply_device_limit(client: dict) -> dict:
    """limitIp в x-ui — макс. одновременных подключений с разных IP."""
    out = dict(client)
    out["limitIp"] = vpn_device_limit_ip()
    return out


def tcp_mirror_email(email: str) -> str:
    """x-ui: email уникален в client_traffics — на TCP inbound зеркало с суффиксом, тот же uuid."""
    suffix = os.getenv("TCP_CLIENT_EMAIL_SUFFIX", "__tcp")
    e = (email or "").strip()
    if not e or e.endswith(suffix):
        return e
    return f"{e}{suffix}"


def xhttp_mirror_email(email: str) -> str:
    suffix = os.getenv("XHTTP_CLIENT_EMAIL_SUFFIX", "__xhttp")
    e = (email or "").strip()
    if not e or e.endswith(suffix):
        return e
    return f"{e}{suffix}"


def _happ_header_text(text: str) -> str:
    """Happ принимает UTF-8 через base64: в HTTP-заголовках только latin-1."""
    raw = (text or "").strip()[:200]
    if not raw.isascii():
        return "base64:" + base64.b64encode(raw.encode("utf-8")).decode("ascii")
    return raw


def happ_subscription_headers(user_id: int | None = None, *, key: Any = None) -> dict[str, str]:
    from happ_json_config import (
        BOT_TELEGRAM_URL,
        PROFILE_UPDATE_INTERVAL,
        get_traffic_bytes,
        is_expired,
        parse_expiry_ts,
        subscription_userinfo,
    )

    title = CFG.vpn_profile_name or "TritonVPN"
    limit = max(1, int(CFG.vpn_max_devices or 2))
    bot_url = os.getenv("BOT_TELEGRAM_URL", BOT_TELEGRAM_URL).strip() or BOT_TELEGRAM_URL
    update_h = os.getenv("PROFILE_UPDATE_INTERVAL", PROFILE_UPDATE_INTERVAL).strip() or "1"

    if key is None and user_id:
        key = get_active_key(user_id)
    expired = False
    if key:
        expired = is_expired(row_get(key, "expires_at"))

    if expired:
        info = "Срок вашей подписки истёк."
        info_color = "red"
        announce = "Продлите подписку в Telegram-боте."
    else:
        info = f"{user_id} • Нажмите 🔄, если не работает VPN" if user_id else "Нажмите 🔄, если не работает VPN"
        info_color = os.getenv("VPN_DEVICE_LIMIT_COLOR", "blue").strip() or "blue"
        announce = f"{user_id} • Нажмите 🔄, если не работает VPN" if user_id else "Нажмите 🔄, если не работает VPN"

    headers: dict[str, str] = {
        "profile-title": title,
        "content-disposition": f'attachment; filename="{title}"',
        "profile-update-interval": update_h,
        "profile-web-page-url": bot_url,
        "sub-expire": "true",
        "sub-expire-button-link": bot_url,
        "sub-info-text": _happ_header_text(info),
        "sub-info-color": info_color,
        "announce": _happ_header_text(announce),
    }
    if key:
        email = row_get(key, "email", "") or ""
        up, down = get_traffic_bytes(email)
        exp_ts = parse_expiry_ts(row_get(key, "expires_at"))
        if exp_ts:
            headers["subscription-userinfo"] = subscription_userinfo(
                upload=up, download=down, expire_ts=exp_ts,
            )
    length, interval, packets = happ_fragment_parts()
    headers.update({
        "fragmentation-enable": "0",
        "fragmentation-packets": packets,
        "fragmentation-length": length,
        "fragmentation-interval": interval,
        "ping-type": "tcp",
        "no-limit-xhttp-enabled": "true",
        "subscriptions-collapse": "false",
    })
    # Ultima-style: profile-title as base64
    try:
        import base64 as _b64
        headers["profile-title"] = "base64:" + _b64.b64encode(title.encode("utf-8")).decode("ascii")
    except Exception:
        pass
    return headers


def format_happ_subscription_body(vless_link: str) -> str:
    length, interval, packets = happ_fragment_parts()
    link = append_happ_fragment_to_vless(vless_link)
    return (
        f"#profile-title: {CFG.vpn_profile_name or 'TritonVPN'}\n"
        f"#fragmentation-enable: 1\n"
        f"#fragmentation-packets: {packets}\n"
        f"#fragmentation-length: {length}\n"
        f"#fragmentation-interval: {interval}\n"
        f"{link}\n"
    )


def xui_subscription_link(sub_id: str) -> str:
    sub_id = (sub_id or "").strip()
    if not sub_id:
        return ""
    return f"{CFG.subscription_base_url.rstrip('/')}/{sub_id}"


def user_facing_subscription_link(user_id: int) -> str:
    """Подписка для Happ: miniapp/sub. JSON — fragment внутри конфига."""
    base = pretty_subscription_link(user_id)
    profile = urllib.parse.quote(CFG.vpn_profile_name or "TritonVPN", safe="")
    if CFG.subscription_format in ("json", "1", "true", "yes"):
        return f"{base}#{profile}"
    if CFG.happ_fragment:
        return f"{base}#{profile}?fragment={CFG.happ_fragment}"
    return f"{base}#{profile}"


def extract_sub_id(subscription_url: str) -> str:
    url = (subscription_url or "").strip().rstrip("/")
    if not url:
        return ""
    return url.split("/")[-1]


def parse_dt(value: Any) -> Optional[datetime]:
    if not value:
        return None
    if isinstance(value, datetime):
        dt = value
    else:
        try:
            dt = datetime.fromisoformat(str(value))
        except Exception:
            return None
    if dt.tzinfo is not None:
        dt = dt.astimezone().replace(tzinfo=None)
    return dt


def add_days_to_date(expires_at: Optional[datetime], days: int) -> datetime:
    base = expires_at if expires_at and expires_at > now() else now()
    return base + timedelta(days=days)


def compute_discount(devices_count: int) -> float:
    if devices_count >= 10: return 0.40
    if devices_count >= 7:  return 0.30
    if devices_count >= 5:  return 0.25
    if devices_count >= 3:  return 0.20
    return 0.0


def calculate_tariff_amount(tariff_id: str, devices_count: int) -> float:
    if tariff_id not in TARIFFS:
        return 0.0
    base_price = TARIFFS[tariff_id]["price"]
    discount = compute_discount(devices_count)
    return round(base_price * devices_count * (1 - discount), 2)


def fmt_dt(value: Any) -> str:
    dt = parse_dt(value)
    if not dt:
        return "—"
    return dt.strftime("%d.%m.%Y %H:%M")


def row_get(row: Any, key: str, default: Any = None) -> Any:
    """Безопасное чтение из sqlite3.Row (не поддерживает .get())"""
    try:
        val = row[key]
        return val if val is not None else default
    except (IndexError, KeyError):
        return default


INSTALL_INSTRUCTION = (
    "📱 <b>Быстрая настройка</b>\n"
    "<b>Телефон (рекомендуем)</b>\n"
    "1. Установите <b>Happ</b> / <b>Happ Plus</b>\n"
    "2. <b>+</b> → импорт подписки или ключа из буфера\n"
    "3. Happ → Настройки → Туннель → включите <b>«Использовать фрагментирование»</b>\n"
    "4. Режим <b>VPN</b>, DNS <b>Remote</b> → включите VPN\n\n"
    "<b>Android (альтернатива)</b>\n"
    "• <b>v2rayNG</b> — глобальный прокси, импорт из буфера\n\n"
    "<b>iPhone (альтернатива)</b>\n"
    "• <b>V2RayTun</b> — Paste from clipboard\n\n"
    "<b>Компьютер</b>\n"
    "• <b>Hiddify</b> или <b>v2rayN</b> / <b>V2RayU</b>\n\n"
    "💡 Если сайты не открываются — Happ → Настройки → Туннель → <b>Использовать фрагментирование</b> ВКЛ\n\n"
    "⚠️ <b>Важно:</b> ключ персональный — не передавайте другим\n"
    f"Поддержка: @{CFG.support_username}"
)

VPN_PROFILE_HINT = (
    "📖 <b>Какой профиль выбрать в Happ</b>\n\n"
    "В подписке <b>7 профилей</b>:\n\n"
    "🤖 <b>Auto</b> — рекомендуем по умолчанию.\n"
    "Сам выбирает быстрый канал (gRPC/XHTTP/TCP), RU-сайты напрямую.\n\n"
    "📡 <b>Hysteria LTE</b> — UDP/QUIC, лучше на мобильном LTE/4G.\n"
    "Обновите подписку и выберите этот профиль при слабом 4G.\n\n"
    "🚀 <b>Турбо</b> — максимальная скорость, один канал gRPC.\n"
    "Дома и на Wi‑Fi.\n\n"
    "⚡ <b>Быстрый</b> — стандартный gRPC.\n\n"
    "🛡 <b>Антиблок</b> — если «Быстрый» не подключается в LTE.\n\n"
    "🇫🇮 <b>Обход всего</b> — xHTTP для сложных сетей (4G/парковка).\n\n"
    "🇷🇺 <b>YouTube</b> — без рекламы + балансер для Google/YouTube.\n\n"
    "💡 Сначала «Auto», на LTE — «Hysteria LTE» или «Обход всего».\n\n"
    "📱 Одновременно до 2 устройств на подписку."
)

VPN_TROUBLESHOOT_CHECKLIST = (
    "🔧 <b>VPN не работает — чеклист</b>\n\n"
    "Пройдите по шагам по порядку:\n\n"
    "1️⃣ <b>Обновите подписку в Happ</b>\n"
    "   Подписки → TritonVPN → потяните вниз / «Обновить»\n\n"
    "2️⃣ <b>Выберите профиль</b>\n"
    "   🤖 Auto — по умолчанию\n"
    "   📡 Hysteria LTE — мобильный LTE/4G\n"
    "   🇫🇮 Обход всего — если не работает на 4G\n"
    "   🛡 Антиблок — запасной вариант\n\n"
    "3️⃣ <b>Проверьте срок подписки</b>\n"
    "   Раздел «Профиль» в боте или мини-приложении\n\n"
    "4️⃣ <b>Отключите лишние устройства</b>\n"
    "   На подписке лимит <b>2 устройства</b> одновременно\n\n"
    "5️⃣ <b>Переустановите подписку</b>\n"
    "   Мини-приложение → «Установка и настройка»\n\n"
    "6️⃣ <b>Всё ещё не работает?</b>\n"
    f"   Напишите в поддержку: @{CFG.support_username}"
)

QUICK_CONNECT_STEPS = (
    "<b>3 шага:</b>\n"
    "1️⃣ Установите <b>Happ</b> или <b>INCY</b> на телефон\n"
    "2️⃣ Нажмите кнопку «Добавить в Happ» или «Добавить в INCY»\n"
    "3️⃣ Включите VPN — профиль <b>🤖 Auto</b> или <b>📡 Hysteria LTE</b>\n\n"
    "💡 Не работает на 4G? Профиль <b>📡 Hysteria LTE</b> или <b>🇫🇮 Обход всего</b>"
)


# =============================================================================
# DATABASE
# =============================================================================

class DB:
    def __init__(self, path: str):
        self.path = path

    def connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        return conn

    def execute(self, query: str, params: tuple = ()) -> None:
        with closing(self.connect()) as conn:
            conn.execute(query, params)
            conn.commit()

    def fetchone(self, query: str, params: tuple = ()) -> Optional[sqlite3.Row]:
        with closing(self.connect()) as conn:
            return conn.execute(query, params).fetchone()

    def fetchall(self, query: str, params: tuple = ()) -> list:
        with closing(self.connect()) as conn:
            return conn.execute(query, params).fetchall()

    def init(self) -> None:
        if os.path.dirname(self.path):
            os.makedirs(os.path.dirname(self.path), exist_ok=True)
        with closing(self.connect()) as conn:
            c = conn.cursor()
            c.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    user_id INTEGER PRIMARY KEY,
                    username TEXT DEFAULT '',
                    first_name TEXT DEFAULT '',
                    last_name TEXT DEFAULT '',
                    balance REAL DEFAULT 0,
                    trial_used INTEGER DEFAULT 0,
                    subscription_end TEXT,
                    referral_code TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            """)
            c.execute("""
                CREATE TABLE IF NOT EXISTS payments (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    amount REAL NOT NULL,
                    method TEXT NOT NULL,
                    status TEXT DEFAULT 'pending',
                    order_id TEXT,
                    payment_id TEXT,
                    tariff_id TEXT,
                    devices_count INTEGER DEFAULT 1,
                    auto_renew_enabled INTEGER DEFAULT 0,
                    payload_json TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    completed_at TEXT
                )
            """)
            c.execute("""
                CREATE TABLE IF NOT EXISTS balance_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    amount REAL NOT NULL,
                    operation_type TEXT NOT NULL,
                    description TEXT,
                    balance_before REAL,
                    balance_after REAL,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            """)
            c.execute("""
                CREATE TABLE IF NOT EXISTS keys (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    email TEXT NOT NULL,
                    vless_link TEXT,
                    subscription_url TEXT DEFAULT '',
                    expires_at TEXT,
                    is_active INTEGER DEFAULT 1,
                    notified_expired INTEGER DEFAULT 0,
                    notified_3days INTEGER DEFAULT 0,
                    notified_1day INTEGER DEFAULT 0,
                    notified_today INTEGER DEFAULT 0,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            """)
            c.execute("""
                CREATE TABLE IF NOT EXISTS referrals (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    referrer_id INTEGER,
                    referred_id INTEGER,
                    bonus INTEGER DEFAULT 0,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            """)
            c.execute("""
                CREATE TABLE IF NOT EXISTS crypto_payments (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    invoice_id TEXT,
                    amount REAL,
                    asset TEXT,
                    status TEXT DEFAULT 'pending',
                    tariff_id TEXT,
                    devices_count INTEGER DEFAULT 1,
                    auto_renew_enabled INTEGER DEFAULT 0,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            """)
            c.execute("""
                CREATE TABLE IF NOT EXISTS purchase_locks (
                    user_id INTEGER PRIMARY KEY,
                    tariff_id TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            """)
            c.execute("""
                CREATE TABLE IF NOT EXISTS tariff_orders (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    order_id TEXT UNIQUE,
                    user_id INTEGER NOT NULL,
                    tariff_id TEXT NOT NULL,
                    payment_method TEXT NOT NULL,
                    status TEXT DEFAULT 'pending',
                    devices_count INTEGER DEFAULT 1,
                    auto_renew_enabled INTEGER DEFAULT 0,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            """)
            c.execute("""
                CREATE TABLE IF NOT EXISTS subscriptions (
                    user_id INTEGER PRIMARY KEY,
                    tariff_id TEXT NOT NULL,
                    devices_count INTEGER DEFAULT 1,
                    status TEXT DEFAULT 'inactive',
                    expires_at TEXT,
                    auto_renew INTEGER DEFAULT 0,
                    payment_method TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            """)
            c.execute("""
                CREATE TABLE IF NOT EXISTS web_sessions (
                    token TEXT PRIMARY KEY,
                    user_id INTEGER NOT NULL,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            """)
            c.execute("""
                CREATE TABLE IF NOT EXISTS promo_codes (
                    code TEXT PRIMARY KEY,
                    percent_off INTEGER NOT NULL DEFAULT 10,
                    max_redemptions INTEGER,
                    redemptions INTEGER DEFAULT 0,
                    expires_at TEXT,
                    active INTEGER DEFAULT 1
                )
            """)
            c.execute("""
                CREATE TABLE IF NOT EXISTS promo_redemptions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    code TEXT NOT NULL,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(user_id, code)
                )
            """)
            c.execute("""
                CREATE TABLE IF NOT EXISTS trial_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    source TEXT DEFAULT '',
                    expires_at TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            """)
            c.execute("""
                CREATE TABLE IF NOT EXISTS user_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    event TEXT NOT NULL,
                    meta TEXT DEFAULT '',
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            """)
            c.execute(
                "CREATE INDEX IF NOT EXISTS idx_user_events_user_event "
                "ON user_events(user_id, event)"
            )
            # Migrate: add missing columns to existing tables
            def add_col(table, col, col_def):
                existing = [r[1] for r in c.execute(f"PRAGMA table_info({table})").fetchall()]
                if col not in existing:
                    c.execute(f"ALTER TABLE {table} ADD COLUMN {col} {col_def}")

            add_col("users",           "first_name",        "TEXT DEFAULT ''")
            add_col("users",           "last_name",         "TEXT DEFAULT ''")
            add_col("users",           "trial_used",        "INTEGER DEFAULT 0")
            add_col("users",           "subscription_end",  "TEXT")
            add_col("users",           "referral_code",     "TEXT")
            add_col("users",           "wheel_discount_pct","INTEGER DEFAULT 0")
            add_col("payments",        "payload_json",      "TEXT")
            add_col("payments",        "tariff_id",         "TEXT")
            add_col("payments",        "devices_count",     "INTEGER DEFAULT 1")
            add_col("payments",        "auto_renew_enabled","INTEGER DEFAULT 0")
            add_col("keys",            "subscription_url",  "TEXT DEFAULT ''")
            add_col("keys",            "email",             "TEXT DEFAULT ''")
            add_col("keys",            "vless_link",        "TEXT")
            add_col("keys",            "expires_at",        "TEXT")
            add_col("keys",            "is_active",         "INTEGER DEFAULT 1")
            add_col("keys",            "notified_expired",  "INTEGER DEFAULT 0")
            add_col("keys",            "notified_3days",    "INTEGER DEFAULT 0")
            add_col("keys",            "notified_1day",     "INTEGER DEFAULT 0")
            add_col("keys",            "notified_today",    "INTEGER DEFAULT 0")
            add_col("crypto_payments", "tariff_id",         "TEXT")
            add_col("crypto_payments", "devices_count",     "INTEGER DEFAULT 1")
            add_col("crypto_payments", "auto_renew_enabled","INTEGER DEFAULT 0")

            # Unique indexes (ignore if already exist)
            for stmt in [
                "CREATE UNIQUE INDEX IF NOT EXISTS idx_payments_payment_id ON payments(payment_id)",
                "CREATE UNIQUE INDEX IF NOT EXISTS idx_payments_order_id ON payments(order_id)",
                "CREATE UNIQUE INDEX IF NOT EXISTS idx_crypto_invoice_id ON crypto_payments(invoice_id)",
            ]:
                try:
                    c.execute(stmt)
                except Exception:
                    pass
            wheel.ensure_wheel_tables(conn)
            conn.commit()
        logger.info("✅ Database initialized")


db = DB(CFG.db_path)


def log_user_event(user_id: int, event: str, meta: str = "") -> None:
    """
    Лёгкий event-трекинг для drip-аналитики (user_events).
    Никогда не бросает исключений — сбой логирования не должен ломать бота.
    """
    try:
        db.execute(
            "INSERT INTO user_events (user_id, event, meta) VALUES (?, ?, ?)",
            (int(user_id), event, meta or ""),
        )
    except Exception:
        try:
            logger.warning("log_user_event failed: user_id=%s event=%s", user_id, event)
        except Exception:
            pass


class PaymentStates(StatesGroup):
    waiting_amount = State()


# =============================================================================
# PLATEGA CLIENT
# =============================================================================

class PlategaClient:
    def __init__(self) -> None:
        self.merchant_id = CFG.platega_merchant_id.strip()
        self.api_key     = CFG.platega_api_key.strip()
        self.base_url    = CFG.platega_api_url.strip().rstrip("/")

    async def create_payment(
        self,
        amount: float,
        description: str,
        user_id: int,
        order_id: Optional[str] = None,
        extra_payload: Optional[dict] = None,
        payment_method: Optional[str] = None,
    ) -> dict:
        if not self.merchant_id or not self.api_key:
            return {"success": False, "error": "PLATEGA credentials not configured"}
        if not order_id:
            order_id = f"order_{user_id}_{int(now().timestamp())}"
        meta: dict = {"user_id": user_id, "order_id": order_id}
        if extra_payload:
            meta.update(extra_payload)
        payload = {
            "paymentMethod": 2,
            "paymentDetails": {"amount": float(amount), "currency": "RUB"},
            "description": description,
            "payload": json.dumps(meta, ensure_ascii=False),
        }
        headers = {
            "X-MerchantId": self.merchant_id,
            "X-Secret":     self.api_key,
            "Content-Type": "application/json",
        }
        try:
            import aiohttp as _aiohttp
            timeout = _aiohttp.ClientTimeout(total=CFG.api_timeout)
            async with _aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.base_url}/transaction/process",
                    headers=headers,
                    json=payload,
                    timeout=timeout,
                ) as response:
                    text = await response.text()
                    status_code = response.status
                    logger.info("PLATEGA STATUS: %s | %s", status_code, text)
                    try:
                        result = json.loads(text)
                    except Exception:
                        result = {"raw": text}
                    if status_code == 200:
                        return {
                            "success":    True,
                            "payment_url": (result.get("redirect") or result.get("payment_url") or result.get("url")),
                            "qr_code":    result.get("qr"),
                            "order_id":   order_id,
                            "payment_id": str(result.get("transactionId") or result.get("id") or ""),
                            "status":     result.get("status"),
                            "raw":        result,
                        }
                    return {"success": False, "error": result}
        except Exception as e:
            logger.exception("Platega create payment failed")
            return {"success": False, "error": str(e)}

    async def get_payment_status(self, payment_id: str) -> Optional[dict]:
        if not self.merchant_id or not self.api_key or not payment_id:
            return None
        headers = {
            "X-MerchantId": self.merchant_id,
            "X-Secret":     self.api_key,
            "Content-Type": "application/json",
        }
        try:
            import aiohttp as _aiohttp
            timeout = _aiohttp.ClientTimeout(total=CFG.api_timeout)
            async with _aiohttp.ClientSession() as session:
                async with session.get(
                    f"{self.base_url}/transaction/{payment_id}",
                    headers=headers,
                    timeout=timeout,
                ) as response:
                    text = await response.text()
                    try:
                        return json.loads(text)
                    except Exception:
                        return {"raw": text}
        except Exception:
            logger.exception("Platega get payment status failed")
            return None


# =============================================================================
# CRYPTOBOT CLIENT
# =============================================================================

class CryptoBotClient:
    def __init__(self) -> None:
        self.token   = CFG.crypto_token.strip()
        self.api_url = CFG.crypto_api_url.strip().rstrip("/")
        self.session = requests.Session()
        if self.token:
            self.session.headers.update({"Crypto-Pay-API-Token": self.token})

    def create_invoice(self, amount_rub: float, asset: str = "USDT", user_id: Optional[int] = None) -> dict:
        if not self.token:
            return {"success": False, "error": "CRYPTO_TOKEN not configured"}
        try:
            rates = {"USDT": 90.0, "TON": 450.0, "BTC": 8500000.0, "ETH": 90000.0}
            rate  = rates.get(asset, 90.0)
            crypto_amount = round(float(amount_rub) / rate, 8)
            payload = {
                "asset":           asset,
                "amount":          str(crypto_amount),
                "description":     f"VPN for user {user_id}",
                "payload":         f"vpn_{user_id}_{int(now().timestamp())}",
                "allow_comments":  False,
                "allow_anonymous": False,
                "expires_in":      3600,
            }
            resp   = self.session.post(f"{self.api_url}/createInvoice", json=payload, timeout=CFG.api_timeout)
            result = resp.json()
            if result.get("ok"):
                data       = result.get("result", {})
                invoice_id = data.get("invoice_id") or data.get("id")
                invoice_url = (
                    data.get("invoice_url") or data.get("pay_url") or data.get("url")
                    or data.get("bot_invoice_url") or data.get("mini_app_invoice_url") or ""
                )
                return {
                    "success":      True,
                    "invoice_url":  invoice_url,
                    "invoice_id":   str(invoice_id),
                    "amount":       float(amount_rub),
                    "asset":        asset,
                    "crypto_amount": crypto_amount,
                }
            err = result.get("error", {})
            error_name = err.get("name") if isinstance(err, dict) else str(err)
            return {"success": False, "error": error_name or "Unknown"}
        except Exception as e:
            logger.exception("CryptoBot create invoice failed")
            return {"success": False, "error": str(e)}

    def get_invoice_status(self, invoice_id: str) -> Optional[str]:
        if not self.token or not invoice_id:
            return None
        try:
            resp   = self.session.post(f"{self.api_url}/getInvoices", json={"invoice_ids": str(invoice_id)}, timeout=CFG.api_timeout)
            result = resp.json()
            if not result.get("ok"):
                return None
            data = result.get("result")
            if isinstance(data, dict):
                items = data.get("items", [])
            elif isinstance(data, list):
                items = data
            else:
                items = []
            return items[0].get("status") if items else None
        except Exception:
            logger.exception("CryptoBot get invoice status failed")
            return None


# =============================================================================
# XUI PANEL — через HTTP API, БЕЗ systemctl restart, БЕЗ прямого SQLite
# =============================================================================

class XUIPanel:
    """
    Управляет клиентами 3x-ui через официальный HTTP API.
    Xray сам применяет изменения без перезапуска.
    НЕ использует systemctl restart. НЕ пишет напрямую в SQLite.
    """

    def __init__(self) -> None:
        self.session    = requests.Session()
        self.session.verify = False
        self._logged_in = False
        # BASE_URL = https://127.0.0.1:18443/Mqrn6QzOKCSAP1pUZD
        # webBasePath в 3x-ui включён → API эндпоинты тоже содержат секретный путь:
        #   https://127.0.0.1:18443/Mqrn6QzOKCSAP1pUZD/login
        #   https://127.0.0.1:18443/Mqrn6QzOKCSAP1pUZD/inbound/get/13
        # Если XUI_API_URL задан в .env — используем его (переопределение).
        if CFG.xui_api_url.strip():
            self.base_url = CFG.xui_api_url.strip().rstrip("/")
        else:
            self.base_url = CFG.base_url.rstrip("/")
        logger.info("XUI API base_url: %s", self.base_url)

    # ── Безопасный парсинг ответа ──────────────────────────────────────────────

    @staticmethod
    def _parse_response(resp: requests.Response) -> dict:
        """Парсит ответ от 3x-ui. Никогда не бросает исключение."""
        raw = ""
        try:
            raw = resp.text
            if not raw or not raw.strip():
                logger.error("XUI empty response (status=%s url=%s)", resp.status_code, resp.url)
                return {}
            return resp.json()
        except Exception as e:
            logger.error("XUI JSON parse error: %s | raw=%r | url=%s", e, raw[:200], resp.url)
            return {}

    # ── Auth ──────────────────────────────────────────────────────────────────

    def _csrf_from(self, html: str) -> str:
        import re as _re
        m = _re.search(r'name="csrf-token" content="([^"]+)"', html or "")
        return m.group(1) if m else ""

    def _set_csrf(self, token: str) -> None:
        token = (token or "").strip()
        if not token:
            return
        self.session.headers.update({
            "X-CSRF-Token": token,
            "X-Requested-With": "XMLHttpRequest",
        })

    def _login(self) -> bool:
        try:
            html = ""
            try:
                html = self.session.get(f"{self.base_url}/", timeout=10).text
            except Exception:
                html = ""
            csrf = self._csrf_from(html)
            self._set_csrf(csrf)
            resp = self.session.post(
                f"{self.base_url}/login",
                json={"username": CFG.xui_username, "password": CFG.xui_password},
                timeout=10,
            )
            logger.info("XUI login response: status=%s body=%r", resp.status_code, resp.text[:200])
            data = self._parse_response(resp)
            if data.get("success"):
                self._logged_in = True
                try:
                    html2 = self.session.get(f"{self.base_url}/panel/", timeout=10).text
                    self._set_csrf(self._csrf_from(html2) or csrf)
                except Exception:
                    self._set_csrf(csrf)
                logger.info("XUI login OK csrf=%s", bool(self.session.headers.get("X-CSRF-Token")))
                return True
            logger.error("XUI login failed: status=%s data=%s", resp.status_code, data)
            return False
        except Exception:
            logger.exception("XUI login exception")
            return False

    def _ensure_auth(self) -> bool:
        if self._logged_in:
            try:
                r = self.session.get(f"{self.base_url}/panel/api/inbounds/list", timeout=5)
                data = self._parse_response(r)
                if r.status_code == 200 and data.get("success"):
                    return True
            except Exception:
                pass
            self._logged_in = False
        return self._login()

    # ── Get inbound ───────────────────────────────────────────────────────────

    def _get_inbound(self) -> Optional[dict]:
        if not self._ensure_auth():
            return None
        try:
            r    = self.session.get(f"{self.base_url}/panel/api/inbounds/get/{CFG.inbound_id}", timeout=10)
            data = self._parse_response(r)
            if data.get("success"):
                return data.get("obj")
            logger.error("get_inbound failed: status=%s data=%s", r.status_code, data)
            return None
        except Exception:
            logger.exception("get_inbound exception")
            return None

    def _parse_clients(self, inbound: dict) -> list:
        """Извлекает список клиентов из объекта inbound."""
        try:
            raw = inbound.get("settings", "{}")
            settings = json.loads(raw) if isinstance(raw, str) else raw
            return settings.get("clients", [])
        except Exception:
            return []

    # ── Add client ────────────────────────────────────────────────────────────

    def add_client(self, email: str, days: int = 30, *, restart_xray: bool = True, _retry: int = 0) -> Optional[dict]:
        if not self._ensure_auth():
            logger.error("add_client: auth failed")
            return None
        try:
            import re as _re
            import sqlite3 as _sq
            client_id  = str(uuid.uuid4())
            sub_id     = str(uuid.uuid4()).replace("-", "")[:16]
            expiry_ts  = int((now() + timedelta(days=days)).timestamp() * 1000)
            safe = "".join(ch if ch.isascii() and (ch.isalnum() or ch in "._-") else "_" for ch in (email or ""))
            safe = _re.sub(r"_+", "_", safe).strip("._-")[:60] or ("u_" + client_id.split("-")[0])
            new_client = apply_device_limit({
                "id":         client_id,
                "email":      safe,
                "enable":     True,
                "flow":       "",
                "totalGB":    0,
                "expiryTime": expiry_ts,
                "reset":      0,
                "subId":      sub_id,
                "tgId":       0,
                "comment":    "",
            })
            inbound_ids = [int(x) for x in os.getenv("NL_XUI_INBOUND_IDS", "1,2,3").split(",") if x.strip()]
            payload = [{
                "client": {
                    "id": new_client["id"],
                    "email": safe,
                    "enable": True,
                    "limitIp": int(new_client.get("limitIp") or 3),
                    "totalGB": 0,
                    "expiryTime": expiry_ts,
                    "flow": "",
                    "subId": sub_id,
                    "comment": "",
                },
                "inboundIds": inbound_ids or [1, 2, 3],
            }]
            r    = self.session.post(f"{self.base_url}/panel/api/clients/bulkCreate", json=payload, timeout=30)
            data = self._parse_response(r)
            obj = data.get("obj") if isinstance(data.get("obj"), dict) else {}
            created = int((obj or {}).get("created") or 0)
            if data.get("success") and created:
                logger.info("XUI add_client bulkCreate OK: email=%s created=%s", safe, created)
                try:
                    db = _sq.connect("/etc/x-ui/x-ui.db")
                    row = db.execute("SELECT id FROM clients WHERE uuid=?", (client_id,)).fetchone()
                    if row:
                        db.execute(
                            "UPDATE client_inbounds SET flow_override=? WHERE client_id=? AND inbound_id=?",
                            ("xtls-rprx-vision", row[0], int(CFG.tcp_inbound_id or 2)),
                        )
                        db.commit()
                    db.close()
                except Exception:
                    logger.exception("add_client flow_override failed")
                if restart_xray:
                    self.restart_xray()
                return new_client
            # retry once after re-auth (CSRF/session). Cap to avoid 403 recursion.
            if (r.status_code in (401, 403) or "not logged" in str(data).lower()) and _retry < 1:
                self._logged_in = False
                if self._login():
                    return self.add_client(email, days, restart_xray=restart_xray, _retry=_retry + 1)
            logger.error("add_client API error: status=%s data=%s", r.status_code, data)
            return None
        except Exception:
            logger.exception("add_client exception")
            return None

    # ── Update expiry ─────────────────────────────────────────────────────────

    # --- Restart Xray -------------------------------------------------
    def restart_xray(self, _retry: int = 0) -> bool:
        """Перезапускает Xray — нужно после addClient/updateClient,
        иначе xray не перечитает bin/config.json и новые клиенты не работают."""
        if not self._ensure_auth():
            logger.error("restart_xray: auth failed")
            return False
        try:
            r = self.session.post(
                f"{self.base_url}/panel/api/server/restartXrayService",
                timeout=20,
            )
            data = self._parse_response(r)
            if data.get("success"):
                logger.info("XUI restart_xray OK")
                return True
            if (r.status_code in (401, 403) or "not logged" in str(data).lower()) and _retry < 1:
                self._logged_in = False
                if self._login():
                    return self.restart_xray(_retry=_retry + 1)
            logger.error("restart_xray failed: status=%s data=%s", r.status_code, data)
            return False
        except Exception:
            logger.exception("restart_xray exception")
            return False


    def _sqlite_set_expiry(self, client_uuid: str, new_expiry_ts: int, enable: int = 1) -> bool:
        try:
            import sqlite3 as _sq
            db = _sq.connect("/etc/x-ui/x-ui.db")
            n = db.execute(
                "UPDATE clients SET expiry_time=?, enable=? WHERE uuid=?",
                (int(new_expiry_ts), int(enable), client_uuid),
            ).rowcount
            db.commit()
            db.close()
            logger.info("XUI sqlite expiry uuid=%s rows=%s ts=%s", client_uuid, n, new_expiry_ts)
            return n > 0
        except Exception:
            logger.exception("sqlite expiry update failed uuid=%s", client_uuid)
            return False

    def update_client_expiry(
        self,
        client_uuid: str,
        client_data: dict,
        new_expiry_ts: int,
        *,
        restart_xray: bool = True,
    ) -> bool:
        """Обновляет срок клиента, сохраняя все его поля."""
        if not self._ensure_auth():
            return False
        try:
            updated = apply_device_limit(dict(client_data))
            updated["expiryTime"] = new_expiry_ts
            updated["enable"]     = True
            ok = False
            for path in (
                f"{self.base_url}/panel/api/clients/update/{client_uuid}",
                f"{self.base_url}/panel/api/inbounds/updateClient/{client_uuid}",
            ):
                payload = updated if "clients/update" in path else {
                    "id": CFG.inbound_id,
                    "settings": json.dumps({"clients": [updated]}),
                }
                r = self.session.post(path, json=payload, timeout=15)
                data = self._parse_response(r)
                if data.get("success"):
                    logger.info("XUI update_client_expiry OK: uuid=%s path=%s", client_uuid, path)
                    ok = True
                    break
                logger.warning("update_client_expiry try failed: %s status=%s data=%s", path, r.status_code, data)
            if not ok:
                ok = self._sqlite_set_expiry(client_uuid, new_expiry_ts, 1)
            if ok:
                if restart_xray:
                    self.restart_xray()
                return True
            logger.error("update_client_expiry failed uuid=%s", client_uuid)
            return False
        except Exception:
            logger.exception("update_client_expiry exception")
            return False

    # ── Disable client ────────────────────────────────────────────────────────

    def disable_client(self, email: str) -> bool:
        if not self._ensure_auth():
            return False
        try:
            inbound = self._get_inbound()
            if not inbound:
                return False
            clients = self._parse_clients(inbound)
            target  = next((c for c in clients if c.get("email") == email), None)
            if not target:
                logger.warning("disable_client: email not found: %s — already gone", email)
                return True
            updated = dict(target)
            updated["enable"] = False
            payload = {
                "id":       CFG.inbound_id,
                "settings": json.dumps({"clients": [updated]}),
            }
            r    = self.session.post(f"{self.base_url}/panel/api/inbounds/updateClient/{target['id']}", json=payload, timeout=15)
            data = self._parse_response(r)
            if data.get("success"):
                logger.info("XUI disable_client OK: email=%s", email)
                return True
            if self._sqlite_set_expiry(target["id"], int(target.get("expiryTime") or 0), 0):
                logger.info("XUI disable_client sqlite OK: email=%s", email)
                self.restart_xray()
                return True
            logger.error("disable_client API error: status=%s data=%s", r.status_code, data)
            return False
        except Exception:
            logger.exception("disable_client exception")
            return False

    def sync_client_to_tcp_inbound(self, client: dict, *, restart_xray: bool = False) -> bool:
        """Зеркало клиента на TCP Fast inbound (тот же uuid, email с суффиксом __tcp)."""
        tcp_id = int(CFG.tcp_inbound_id or 0)
        client_uuid = (client.get("id") or "").strip()
        orig_email = (client.get("email") or "").strip()
        if not tcp_id or not client_uuid or not orig_email:
            return True
        suffix = os.getenv("TCP_CLIENT_EMAIL_SUFFIX", "__tcp")
        if orig_email.endswith(suffix):
            return True
        if not self._ensure_auth():
            return False
        try:
            r = self.session.get(f"{self.base_url}/panel/api/inbounds/get/{tcp_id}", timeout=15)
            data = self._parse_response(r)
            if not data.get("success"):
                logger.warning("sync_tcp: get inbound %s failed", tcp_id)
                return False
            ib = data["obj"]
            settings = json.loads(ib.get("settings") or "{}")
            tcp_clients = list(settings.get("clients") or [])
            exists = any((c.get("id") or "") == client_uuid for c in tcp_clients)
            copy = apply_device_limit(dict(client))
            copy["flow"] = os.getenv("TCP_VLESS_FLOW", "xtls-rprx-vision")
            copy["enable"] = True
            copy["email"] = tcp_mirror_email(orig_email)
            payload = {
                "id": tcp_id,
                "settings": json.dumps({"clients": [copy]}, ensure_ascii=False),
            }
            if exists:
                url = f"{self.base_url}/panel/api/inbounds/updateClient/{client_uuid}"
            else:
                url = f"{self.base_url}/panel/api/inbounds/addClient"
            r2 = self.session.post(url, json=payload, timeout=25)
            data2 = self._parse_response(r2)
            if not data2.get("success"):
                logger.warning("sync_tcp: %s failed %s", "update" if exists else "add", data2)
                return False
            logger.info("XUI sync_tcp OK: uuid=%s email=%s", client_uuid, copy.get("email"))
            if restart_xray:
                self.restart_xray()
            return True
        except Exception:
            logger.exception("sync_client_to_tcp_inbound exception")
            return False

    def sync_client_to_xhttp_inbound(self, client: dict, *, restart_xray: bool = False) -> bool:
        """Зеркало клиента на XHTTP LTE inbound (тот же uuid, email с суффиксом __xhttp)."""
        xhttp_id = int(CFG.xhttp_inbound_id or 0)
        client_uuid = (client.get("id") or "").strip()
        orig_email = (client.get("email") or "").strip()
        if not xhttp_id or not client_uuid or not orig_email:
            return True
        suffix = os.getenv("XHTTP_CLIENT_EMAIL_SUFFIX", "__xhttp")
        if orig_email.endswith(suffix):
            return True
        if not self._ensure_auth():
            return False
        try:
            r = self.session.get(f"{self.base_url}/panel/api/inbounds/get/{xhttp_id}", timeout=15)
            data = self._parse_response(r)
            if not data.get("success"):
                logger.warning("sync_xhttp: get inbound %s failed", xhttp_id)
                return False
            ib = data["obj"]
            settings = json.loads(ib.get("settings") or "{}")
            xhttp_clients = list(settings.get("clients") or [])
            exists = any((c.get("id") or "") == client_uuid for c in xhttp_clients)
            copy = apply_device_limit(dict(client))
            copy["flow"] = ""
            copy["enable"] = True
            copy["email"] = xhttp_mirror_email(orig_email)
            payload = {
                "id": xhttp_id,
                "settings": json.dumps({"clients": [copy]}, ensure_ascii=False),
            }
            if exists:
                url = f"{self.base_url}/panel/api/inbounds/updateClient/{client_uuid}"
            else:
                url = f"{self.base_url}/panel/api/inbounds/addClient"
            r2 = self.session.post(url, json=payload, timeout=25)
            data2 = self._parse_response(r2)
            if not data2.get("success"):
                logger.warning("sync_xhttp: %s failed %s", "update" if exists else "add", data2)
                return False
            logger.info("XUI sync_xhttp OK: uuid=%s email=%s", client_uuid, copy.get("email"))
            if restart_xray:
                self.restart_xray()
            return True
        except Exception:
            logger.exception("sync_client_to_xhttp_inbound exception")
            return False

    # ── Delete client ─────────────────────────────────────────────────────────

    def delete_client(self, client_uuid: str) -> bool:
        if not self._ensure_auth():
            return False
        try:
            r    = self.session.post(f"{self.base_url}/panel/api/inbounds/{CFG.inbound_id}/delClient/{client_uuid}", timeout=10)
            data = self._parse_response(r)
            if data.get("success"):
                logger.info("XUI delete_client OK: uuid=%s", client_uuid)
                return True
            logger.error("delete_client failed: status=%s data=%s", r.status_code, data)
            return False
        except Exception:
            logger.exception("delete_client exception")
            return False


platega_client = PlategaClient()
crypto_bot     = CryptoBotClient()
xui            = XUIPanel()
storage        = MemoryStorage()
bot            = Bot(token=CFG.bot_token)
dp             = Dispatcher(storage=storage)


# =============================================================================
# USER & SUBSCRIPTION HELPERS
# =============================================================================

def get_or_create_user_from_tg(tg_user: types.User) -> sqlite3.Row:
    row = db.fetchone("SELECT * FROM users WHERE user_id = ?", (tg_user.id,))
    if row:
        db.execute(
            "UPDATE users SET username=?, first_name=?, last_name=? WHERE user_id=?",
            (tg_user.username or "", tg_user.first_name or "", tg_user.last_name or "", tg_user.id),
        )
    else:
        db.execute(
            "INSERT INTO users (user_id, username, first_name, last_name, referral_code) VALUES (?, ?, ?, ?, ?)",
            (tg_user.id, tg_user.username or "", tg_user.first_name or "", tg_user.last_name or "", generate_ref_code()),
        )
    return db.fetchone("SELECT * FROM users WHERE user_id = ?", (tg_user.id,))


def get_or_create_user_by_webapp(payload_user: dict, start_param: str = "") -> sqlite3.Row:
    user_id    = int(payload_user["id"])
    username   = payload_user.get("username", "")
    first_name = payload_user.get("first_name", "")
    last_name  = payload_user.get("last_name", "")
    row = db.fetchone("SELECT * FROM users WHERE user_id = ?", (user_id,))
    if row:
        db.execute(
            "UPDATE users SET username=?, first_name=?, last_name=? WHERE user_id=?",
            (username, first_name, last_name, user_id),
        )
    else:
        db.execute(
            "INSERT INTO users (user_id, username, first_name, last_name, referral_code) VALUES (?, ?, ?, ?, ?)",
            (user_id, username, first_name, last_name, generate_ref_code()),
        )
        # Реферальная логика — только для новых юзеров
        if start_param:
            ref = start_param.strip()
            if ref and ref != str(user_id):
                owner = db.fetchone("SELECT user_id FROM users WHERE referral_code = ?", (ref,))
                already = db.fetchone("SELECT id FROM referrals WHERE referred_id = ?", (user_id,))
                if owner and int(owner["user_id"]) != user_id and not already:
                    db.execute(
                        "INSERT INTO referrals (referrer_id, referred_id, bonus) VALUES (?, ?, ?)",
                        (int(owner["user_id"]), user_id, 0),
                    )
                    try:
                        logger.info("referral (webapp): user %s invited %s", owner["user_id"], user_id)
                    except Exception:
                        pass
    return db.fetchone("SELECT * FROM users WHERE user_id = ?", (user_id,))


def get_balance(user_id: int) -> float:
    row = db.fetchone("SELECT balance FROM users WHERE user_id = ?", (user_id,))
    return float(row["balance"]) if row else 0.0


def add_balance(user_id: int, amount: float, operation_type: str, description: str) -> float:
    old_balance = get_balance(user_id)
    new_balance = round(old_balance + float(amount), 2)
    with closing(db.connect()) as conn:
        cur = conn.cursor()
        cur.execute("UPDATE users SET balance = ? WHERE user_id = ?", (new_balance, user_id))
        cur.execute(
            "INSERT INTO balance_history (user_id, amount, operation_type, description, balance_before, balance_after) VALUES (?, ?, ?, ?, ?, ?)",
            (user_id, float(amount), operation_type, description, old_balance, new_balance),
        )
        conn.commit()
    return new_balance


def deduct_balance(user_id: int, amount: float, operation_type: str, description: str) -> tuple[bool, float]:
    old_balance = get_balance(user_id)
    amount = round(float(amount), 2)
    if amount <= 0 or old_balance < amount:
        return False, old_balance
    new_balance = round(old_balance - amount, 2)
    with closing(db.connect()) as conn:
        cur = conn.cursor()
        cur.execute("UPDATE users SET balance = ? WHERE user_id = ?", (new_balance, user_id))
        cur.execute(
            "INSERT INTO balance_history (user_id, amount, operation_type, description, balance_before, balance_after) VALUES (?, ?, ?, ?, ?, ?)",
            (user_id, -amount, operation_type, description, old_balance, new_balance),
        )
        conn.commit()
    return True, new_balance


def acquire_purchase_lock(user_id: int, tariff_id: str) -> bool:
    try:
        with closing(db.connect()) as conn:
            conn.execute("INSERT INTO purchase_locks (user_id, tariff_id) VALUES (?, ?)", (user_id, tariff_id))
            conn.commit()
        return True
    except Exception:
        return False


def release_purchase_lock(user_id: int) -> None:
    db.execute("DELETE FROM purchase_locks WHERE user_id = ?", (user_id,))


def get_subscription(user_id: int) -> Optional[sqlite3.Row]:
    return db.fetchone("SELECT * FROM subscriptions WHERE user_id = ?", (user_id,))


def upsert_subscription(user_id: int, tariff_id: str, devices_count: int, payment_method: str, auto_renew: bool) -> datetime:
    if tariff_id not in TARIFFS:
        logger.error("upsert_subscription: unknown tariff_id=%s", tariff_id)
        return now() + timedelta(days=30)
    devices_count = min(max(1, int(devices_count or 1)), max(1, int(CFG.vpn_max_devices or 2)))
    tariff      = TARIFFS[tariff_id]
    current     = get_subscription(user_id)
    current_exp = parse_dt(current["expires_at"]) if current else None
    key_row     = get_active_key(user_id)
    key_exp     = parse_dt(key_row["expires_at"]) if key_row else None
    base_exp    = current_exp
    if key_exp and (base_exp is None or key_exp > base_exp):
        base_exp = key_exp
    new_exp     = add_days_to_date(base_exp, tariff["days"])
    if current:
        db.execute(
            "UPDATE subscriptions SET tariff_id=?, devices_count=?, status='active', expires_at=?, auto_renew=?, payment_method=?, updated_at=CURRENT_TIMESTAMP WHERE user_id=?",
            (tariff_id, devices_count, new_exp.isoformat(), 1 if auto_renew else 0, payment_method, user_id),
        )
    else:
        db.execute(
            "INSERT INTO subscriptions (user_id, tariff_id, devices_count, status, expires_at, auto_renew, payment_method) VALUES (?, ?, ?, 'active', ?, ?, ?)",
            (user_id, tariff_id, devices_count, new_exp.isoformat(), 1 if auto_renew else 0, payment_method),
        )
    db.execute("UPDATE users SET subscription_end = ? WHERE user_id = ?", (new_exp.isoformat(), user_id))
    return new_exp


def get_active_key(user_id: int) -> Optional[sqlite3.Row]:
    return db.fetchone(
        "SELECT * FROM keys WHERE user_id = ? AND is_active = 1 ORDER BY id DESC LIMIT 1",
        (user_id,),
    )


def get_all_keys(user_id: int) -> list:
    return db.fetchall("SELECT * FROM keys WHERE user_id = ? ORDER BY id DESC", (user_id,))


def resolve_tariff_id_for_order(
    meta: dict,
    order_id: Optional[str] = None,
    transaction_id: Optional[str] = None,
) -> Optional[str]:
    """Тариф из webhook meta; если пусто — из tariff_orders / payments (pending)."""
    tid = str(meta.get("tariff_id") or meta.get("plan") or "").strip()
    if tid in TARIFFS:
        return tid
    if order_id:
        row = db.fetchone("SELECT tariff_id FROM tariff_orders WHERE order_id = ?", (order_id,))
        if row and row["tariff_id"] in TARIFFS:
            return str(row["tariff_id"])
        row = db.fetchone(
            "SELECT tariff_id FROM payments WHERE order_id = ? AND tariff_id IS NOT NULL AND tariff_id != ''",
            (order_id,),
        )
        if row and row["tariff_id"] in TARIFFS:
            return str(row["tariff_id"])
    if transaction_id:
        row = db.fetchone(
            "SELECT tariff_id FROM payments WHERE payment_id = ? AND tariff_id IS NOT NULL AND tariff_id != ''",
            (transaction_id,),
        )
        if row and row["tariff_id"] in TARIFFS:
            return str(row["tariff_id"])
    return None


def reset_key_expiry_notifications(*, key_id: int | None = None, user_id: int | None = None) -> None:
    """Сбрасывает флаги уведомлений об истечении при продлении подписки."""
    if key_id is not None:
        db.execute(
            "UPDATE keys SET notified_3days = 0, notified_1day = 0, notified_today = 0, "
            "notified_expired = 0, is_active = 1 WHERE id = ?",
            (key_id,),
        )
    elif user_id is not None:
        db.execute(
            "UPDATE keys SET notified_3days = 0, notified_1day = 0, notified_today = 0, "
            "notified_expired = 0, is_active = 1 "
            "WHERE id = (SELECT id FROM keys WHERE user_id = ? ORDER BY id DESC LIMIT 1)",
            (user_id,),
        )


def sync_active_key_expiry(user_id: int, new_exp: datetime) -> None:
    """Выравнивает срок активного ключа в БД и 3X-UI с датой подписки (без повторного +N дней)."""
    key = get_active_key(user_id)
    if not key:
        return
    exp_iso = new_exp.isoformat()
    db.execute(
        "UPDATE keys SET expires_at = ? WHERE user_id = ? AND is_active = 1",
        (exp_iso, user_id),
    )
    reset_key_expiry_notifications(key_id=int(key["id"]))
    inbound = xui._get_inbound()
    if not inbound:
        logger.warning("sync_active_key_expiry: inbound unavailable user_id=%s", user_id)
        return
    clients = xui._parse_clients(inbound)
    target = next((c for c in clients if c.get("email") == key["email"]), None)
    if not target:
        logger.warning("sync_active_key_expiry: client %s not in x-ui", key["email"])
        return
    xui.update_client_expiry(target["id"], target, int(new_exp.timestamp() * 1000))


def issue_key_for_user(user_id: int, tariff_id: str) -> tuple[Optional[str], Optional[str], Optional[str], Optional[datetime]]:
    """
    Выдаёт VLESS-ключ:
    - Если есть активный ключ → продлевает срок (ключ НЕ меняется)
    - Если нет → создаёт новый клиент через API
    Возвращает: (email, vless_link, subscription_url, expires_at)
    """
    if tariff_id not in TARIFFS:
        logger.error("issue_key_for_user: unknown tariff_id=%s", tariff_id)
        return None, None, None, None

    days = TARIFFS[tariff_id]["days"]

    existing_key = db.fetchone(
        "SELECT * FROM keys WHERE user_id = ? AND is_active = 1 ORDER BY id DESC LIMIT 1",
        (user_id,),
    )

    if existing_key:
        # ── Продление существующего ключа ─────────────────────────────────
        email            = existing_key["email"]
        vless_link       = existing_key["vless_link"]
        subscription_url = row_get(existing_key, "subscription_url", "")

        current_exp  = parse_dt(existing_key["expires_at"])
        base         = current_exp if (current_exp and current_exp > now()) else now()
        new_exp      = base + timedelta(days=days)
        new_expiry_ts = int(new_exp.timestamp() * 1000)

        # Обновить в x-ui
        inbound = xui._get_inbound()
        if inbound:
            try:
                clients = xui._parse_clients(inbound)
                target  = next((c for c in clients if c.get("email") == email), None)
                if target:
                    xui.update_client_expiry(target["id"], target, new_expiry_ts)
                    vless_link = make_vless_link(target["id"], email)
                    subscription_url = user_facing_subscription_link(user_id)
                else:
                    # Клиент пропал из x-ui — пересоздаём
                    logger.warning("issue_key: %s not in x-ui, recreating", email)
                    new_client = xui.add_client(email, days)
                    if not new_client:
                        return None, None, None, None
                    vless_link = make_vless_link(new_client["id"], email)
            except Exception:
                logger.exception("issue_key: error updating expiry in x-ui")
        else:
            logger.warning("issue_key: could not get inbound, skipping x-ui update")

        db.execute(
            "UPDATE keys SET expires_at = ?, vless_link = ?, subscription_url = ? WHERE user_id = ? AND is_active = 1",
            (new_exp.isoformat(), vless_link, subscription_url, user_id),
        )
        reset_key_expiry_notifications(key_id=int(existing_key["id"]))
        logger.info("issue_key: extended for user_id=%s until %s", user_id, new_exp)
        return email, vless_link, subscription_url, new_exp

    else:
        # ── Новый ключ ────────────────────────────────────────────────────
        email = f"{user_id}_{secrets.token_hex(3)}"
        client = xui.add_client(email, days)
        if not client:
            logger.error("issue_key: xui.add_client failed for user_id=%s", user_id)
            return None, None, None, None

        vless_link       = make_vless_link(client["id"], email)
        exp              = now() + timedelta(days=days)
        # Всегда miniapp/sub — x-ui :2096 ломает Happ
        subscription_url = user_facing_subscription_link(user_id)

        db.execute(
            "INSERT INTO keys (user_id, email, vless_link, subscription_url, expires_at, is_active) VALUES (?, ?, ?, ?, ?, 1)",
            (user_id, email, vless_link, subscription_url, exp.isoformat()),
        )
        logger.info("issue_key: created new key for user_id=%s email=%s", user_id, email)
        return email, vless_link, subscription_url, exp

# ────────────────────────────────────────────────────────────
#  REFERRAL BONUS — начисление на баланс при первой оплате друга
# ────────────────────────────────────────────────────────────

async def _grant_referral_bonus(invited_user_id: int) -> None:
    """Начисляет реферальный бонус на баланс пригласителю при первой оплате друга."""
    try:
        ref_row = db.fetchone(
            "SELECT referrer_id, bonus FROM referrals WHERE referred_id = ?",
            (invited_user_id,),
        )
        if not ref_row:
            return
        if float(ref_row["bonus"] or 0) > 0:
            return

        bonus_rub = float(CFG.referral_bonus)
        if bonus_rub <= 0:
            return

        referrer_id = int(ref_row["referrer_id"])
        new_balance = add_balance(
            referrer_id,
            bonus_rub,
            "referral_bonus",
            f"Реферальный бонус за друга {invited_user_id}",
        )

        db.execute(
            "UPDATE referrals SET bonus = ? WHERE referred_id = ?",
            (bonus_rub, invited_user_id),
        )

        try:
            await bot.send_message(
                referrer_id,
                f"🎉 <b>Ваш друг оформил подписку!</b>\n\n"
                f"На баланс начислено <b>{rub(bonus_rub)}</b>.\n"
                f"💰 Текущий баланс: <b>{rub(new_balance)}</b>",
                parse_mode="HTML",
            )
        except Exception:
            logger.exception("referral_bonus: notify failed")

        logger.info(
            "referral_bonus: +%s rub to %s for invited %s",
            bonus_rub, referrer_id, invited_user_id,
        )
    except Exception:
        logger.exception("_grant_referral_bonus failed")


def grant_vpn_bonus_days(user_id: int, days: int, *, restart_xray: bool = True) -> Optional[str]:
    """Продлевает активную подписку/ключ на N дней. Возвращает ISO даты окончания."""
    if days <= 0:
        return None
    try:
        key_row = get_active_key(user_id)
        sub = get_subscription(user_id)
        new_exp: Optional[datetime] = None

        if key_row:
            current_exp = parse_dt(key_row["expires_at"])
            new_exp = add_days_to_date(current_exp, days)
            new_expiry_ts = int(new_exp.timestamp() * 1000)
            try:
                inbound = xui._get_inbound()
                if inbound:
                    clients = xui._parse_clients(inbound)
                    target = next((c for c in clients if c.get("email") == key_row["email"]), None)
                    if target:
                        xui.update_client_expiry(
                            target["id"], target, new_expiry_ts, restart_xray=restart_xray,
                        )
            except Exception:
                logger.exception("grant_vpn_bonus_days: xui update failed user_id=%s", user_id)
            db.execute(
                "UPDATE keys SET expires_at = ? WHERE id = ?",
                (new_exp.isoformat(), key_row["id"]),
            )
            reset_key_expiry_notifications(key_id=int(key_row["id"]))
        elif sub and str(sub["status"] or "") == "active":
            current_exp = parse_dt(sub["expires_at"])
            new_exp = add_days_to_date(current_exp, days)
        else:
            urow = db.fetchone("SELECT subscription_end FROM users WHERE user_id = ?", (user_id,))
            cur_end = parse_dt(urow["subscription_end"]) if urow and urow["subscription_end"] else None
            new_exp = add_days_to_date(cur_end, days)

        if not new_exp:
            return None

        exp_iso = new_exp.isoformat()
        db.execute(
            "UPDATE users SET subscription_end = CASE "
            "  WHEN subscription_end IS NULL OR subscription_end < ? THEN ? "
            "  ELSE subscription_end "
            "END WHERE user_id = ?",
            (exp_iso, exp_iso, user_id),
        )
        if sub:
            db.execute(
                "UPDATE subscriptions SET expires_at = ?, status = 'active', updated_at = CURRENT_TIMESTAMP "
                "WHERE user_id = ?",
                (exp_iso, user_id),
            )
        if key_row and sub:
            sync_active_key_expiry(user_id, new_exp)
        return exp_iso
    except Exception:
        logger.exception("grant_vpn_bonus_days failed user_id=%s days=%s", user_id, days)
        return None


def get_wheel_discount_percent(user_id: int) -> int:
    row = db.fetchone("SELECT wheel_discount_pct FROM users WHERE user_id = ?", (user_id,))
    return int(row["wheel_discount_pct"] or 0) if row else 0


def consume_wheel_discount(user_id: int) -> int:
    pct = get_wheel_discount_percent(user_id)
    if pct > 0:
        db.execute("UPDATE users SET wheel_discount_pct = 0 WHERE user_id = ?", (user_id,))
    return pct


def create_web_session(user_id: int) -> str:
    token = secrets.token_urlsafe(48)
    db.execute("INSERT INTO web_sessions (token, user_id) VALUES (?, ?)", (token, user_id))
    return token


def get_user_id_by_session(token: str) -> Optional[int]:
    row = db.fetchone("SELECT user_id FROM web_sessions WHERE token = ?", (token,))
    return int(row["user_id"]) if row else None


def get_web_auth_account_by_token(token: str) -> Optional[sqlite3.Row]:
    if not (token or "").strip():
        return None
    return db.fetchone(
        f"""
        SELECT a.id AS account_id, a.email, a.telegram_user_id, a.vpn_user_id
        FROM {WEB_AUTH_SESSIONS_TABLE} s
        JOIN web_accounts a ON a.id = s.account_id
        WHERE s.token = ? AND s.expires_at > datetime('now')
        """,
        (token.strip(),),
    )


def ensure_web_vpn_user(account_id: int, email: str) -> int:
    """Гарантирует строку users для веб-аккаунта без Telegram (оплата и ключи на сайте)."""
    row = db.fetchone("SELECT vpn_user_id FROM web_accounts WHERE id = ?", (account_id,))
    if row and row["vpn_user_id"] is not None:
        return int(row["vpn_user_id"])
    uid = WEB_INTERNAL_USER_ID_BASE + int(account_id)
    uname = (email or "web").split("@")[0][:64]
    try:
        db.execute(
            "INSERT INTO users (user_id, username, first_name, last_name, referral_code) VALUES (?, ?, '', '', ?)",
            (uid, uname, generate_ref_code()),
        )
    except sqlite3.IntegrityError:
        pass
    db.execute("UPDATE web_accounts SET vpn_user_id = ? WHERE id = ?", (uid, account_id))
    got = db.fetchone("SELECT vpn_user_id FROM web_accounts WHERE id = ?", (account_id,))
    return int(got["vpn_user_id"]) if got and got["vpn_user_id"] is not None else uid


def merge_web_vpn_into_telegram(synthetic: int, tg_id: int) -> None:
    """Переносит оплату и ключи с веб-синтетического user_id на Telegram user_id."""
    if synthetic == tg_id:
        return
    syn_row = db.fetchone("SELECT user_id FROM users WHERE user_id = ?", (synthetic,))
    if not syn_row:
        return
    sub_s = db.fetchone("SELECT * FROM subscriptions WHERE user_id = ?", (synthetic,))
    sub_t = db.fetchone("SELECT * FROM subscriptions WHERE user_id = ?", (tg_id,))
    with closing(db.connect()) as conn:
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        cur.execute("UPDATE keys SET user_id = ? WHERE user_id = ?", (tg_id, synthetic))
        cur.execute("UPDATE payments SET user_id = ? WHERE user_id = ?", (tg_id, synthetic))
        cur.execute("UPDATE tariff_orders SET user_id = ? WHERE user_id = ?", (tg_id, synthetic))
        cur.execute("UPDATE crypto_payments SET user_id = ? WHERE user_id = ?", (tg_id, synthetic))
        cur.execute("UPDATE balance_history SET user_id = ? WHERE user_id = ?", (tg_id, synthetic))
        cur.execute("UPDATE referrals SET referred_id = ? WHERE referred_id = ?", (tg_id, synthetic))
        cur.execute("UPDATE referrals SET referrer_id = ? WHERE referrer_id = ?", (tg_id, synthetic))
        cur.execute("DELETE FROM purchase_locks WHERE user_id = ?", (tg_id,))
        cur.execute("UPDATE purchase_locks SET user_id = ? WHERE user_id = ?", (tg_id, synthetic))
        if sub_s and sub_t:
            exp_s = parse_dt(sub_s["expires_at"])
            exp_t = parse_dt(sub_t["expires_at"])
            candidates = [x for x in (exp_s, exp_t) if x]
            merged_exp = max(candidates) if candidates else now()
            if exp_s and exp_t:
                tariff_pick = sub_s["tariff_id"] if exp_s >= exp_t else sub_t["tariff_id"]
            elif exp_s:
                tariff_pick = sub_s["tariff_id"]
            else:
                tariff_pick = sub_t["tariff_id"]
            st_pick = (
                "active"
                if (sub_s["status"] == "active" or sub_t["status"] == "active")
                else (sub_t["status"] or "inactive")
            )
            dev = max(int(sub_s["devices_count"] or 1), int(sub_t["devices_count"] or 1))
            ar = 1 if int(sub_s["auto_renew"] or 0) + int(sub_t["auto_renew"] or 0) > 0 else 0
            pm = sub_t["payment_method"] or sub_s["payment_method"] or "sbp"
            cur.execute("DELETE FROM subscriptions WHERE user_id IN (?, ?)", (synthetic, tg_id))
            cur.execute(
                """INSERT INTO subscriptions (user_id, tariff_id, devices_count, status, expires_at, auto_renew, payment_method)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (tg_id, tariff_pick, dev, st_pick, merged_exp.isoformat(), ar, pm),
            )
        elif sub_s:
            cur.execute("UPDATE subscriptions SET user_id = ? WHERE user_id = ?", (tg_id, synthetic))
        br = db.fetchone("SELECT balance FROM users WHERE user_id = ?", (synthetic,))
        bal_add = float(br["balance"] or 0) if br else 0.0
        if bal_add:
            cur.execute(
                "UPDATE users SET balance = COALESCE(balance, 0) + ? WHERE user_id = ?",
                (bal_add, tg_id),
            )
        cur.execute("DELETE FROM users WHERE user_id = ?", (synthetic,))
        conn.commit()


def resolve_user_id_from_web_bearer(token: str) -> Optional[int]:
    row = get_web_auth_account_by_token(token)
    if not row:
        return None
    if row["telegram_user_id"] is not None:
        return int(row["telegram_user_id"])
    return ensure_web_vpn_user(int(row["account_id"]), row["email"] or "")


def promo_discount_percent(code: str, user_id: int) -> tuple[int, Optional[str]]:
    c = (code or "").strip().upper()
    if not c:
        return 0, None
    row = db.fetchone("SELECT * FROM promo_codes WHERE code = ? AND active = 1", (c,))
    if not row:
        return 0, "promo_not_found"
    exp_raw = row["expires_at"]
    if exp_raw:
        exp = parse_dt(exp_raw)
        if exp and exp < now():
            return 0, "promo_expired"
    max_r = row["max_redemptions"]
    if max_r is not None and int(row["redemptions"] or 0) >= int(max_r):
        return 0, "promo_exhausted"
    if db.fetchone("SELECT 1 FROM promo_redemptions WHERE user_id = ? AND code = ?", (user_id, c)):
        return 0, "promo_already_used"
    pct = int(row["percent_off"] or 0)
    if pct <= 0 or pct > 90:
        return 0, "promo_invalid"
    return pct, None


def record_promo_redemption(user_id: int, promo_code: str) -> None:
    c = (promo_code or "").strip().upper()
    if not c:
        return
    try:
        db.execute(
            "INSERT INTO promo_redemptions (user_id, code) VALUES (?, ?)",
            (user_id, c),
        )
        db.execute(
            "UPDATE promo_codes SET redemptions = COALESCE(redemptions, 0) + 1 WHERE code = ?",
            (c,),
        )
    except Exception:
        logger.exception("record_promo_redemption failed user_id=%s code=%s", user_id, c)


def verify_telegram_login_widget(widget: dict, bot_token: str) -> Optional[int]:
    """Проверка подписи Telegram Login Widget (не WebApp initData)."""
    if not isinstance(widget, dict):
        return None
    hash_received = widget.get("hash")
    if not hash_received:
        return None
    pairs = []
    for key in sorted(widget.keys()):
        if key == "hash":
            continue
        pairs.append(f"{key}={widget[key]}")
    check_string = "\n".join(pairs)
    secret_key = hashlib.sha256(bot_token.encode()).digest()
    computed = hmac.new(secret_key, check_string.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(computed, str(hash_received)):
        return None
    try:
        auth_date = int(widget.get("auth_date", 0))
    except (TypeError, ValueError):
        return None
    if time.time() - auth_date > 86400:
        return None
    try:
        return int(widget["id"])
    except (KeyError, TypeError, ValueError):
        return None


def parse_bearer_token(request: web.Request) -> Optional[str]:
    header = request.headers.get("Authorization", "")
    if not header.startswith("Bearer "):
        return None
    return header.split(" ", 1)[1].strip()


def validate_telegram_init_data(init_data: str, bot_token: str) -> Optional[dict]:
    try:
        parsed    = urllib.parse.parse_qsl(init_data, keep_blank_values=True)
        data      = dict(parsed)
        recv_hash = data.pop("hash", None)
        if not recv_hash:
            return None
        check_str  = "\n".join(f"{k}={v}" for k, v in sorted(data.items()))
        secret_key = hmac.new(b"WebAppData", bot_token.encode(), hashlib.sha256).digest()
        calc_hash  = hmac.new(secret_key, check_str.encode(), hashlib.sha256).hexdigest()
        if calc_hash != recv_hash:
            return None
        if time.time() - int(data.get("auth_date", "0")) > 86400:
            return None
        user_json = data.get("user")
        if not user_json:
            return None
        return json.loads(user_json)
    except Exception:
        logger.exception("Telegram init data validation failed")
        return None


def json_response(payload: dict, status: int = 200) -> web.Response:
    return web.Response(
        text=json.dumps(payload, ensure_ascii=False),
        status=status,
        content_type="application/json",
    )


async def auth_required(request: web.Request) -> Optional[int]:
    token = parse_bearer_token(request)
    if token:
        uid = get_user_id_by_session(token)
        if uid is not None:
            return uid
        linked = resolve_user_id_from_web_bearer(token)
        if linked is not None:
            return linked
    init_data = request.headers.get("X-Telegram-Init-Data", "")
    if init_data:
        tg_user = validate_telegram_init_data(init_data, CFG.bot_token)
        if tg_user:
            # Извлекаем start_param из 3 источников (приоритет: initData > header > Referer)
            start_param = ""
            # Источник 1: initData
            try:
                parsed_qs = urllib.parse.parse_qs(init_data, keep_blank_values=True)
                start_param = (parsed_qs.get("start_param", [""]) or [""])[0].strip()
            except Exception:
                pass
            # Источник 2: явный header от mini app
            if not start_param:
                start_param = (request.headers.get("X-Telegram-Start-Param", "") or "").strip()
            # Источник 3: fallback — Referer URL (?tgWebAppStartParam=...)
            if not start_param:
                try:
                    referer = request.headers.get("Referer", "") or ""
                    if referer:
                        ref_qs = urllib.parse.parse_qs(urllib.parse.urlparse(referer).query)
                        start_param = (ref_qs.get("tgWebAppStartParam", [""]) or [""])[0].strip()
                except Exception:
                    pass
            try:
                if start_param:
                    logger.info("auth_required: start_param=%s detected", start_param)
            except Exception:
                pass
            user = get_or_create_user_by_webapp(tg_user, start_param=start_param)
            return int(user["user_id"])
    return None


def user_stats_payload(user_id: int) -> dict:
    user       = db.fetchone("SELECT * FROM users WHERE user_id = ?", (user_id,))
    sub        = get_subscription(user_id)
    active_key = get_active_key(user_id)
    all_keys   = get_all_keys(user_id)
    refs_count_row  = db.fetchone("SELECT COUNT(*) AS c FROM referrals WHERE referrer_id = ?", (user_id,))
    refs_bonus_row  = db.fetchone("SELECT COALESCE(SUM(bonus), 0) AS s FROM referrals WHERE referrer_id = ?", (user_id,))
    refs_count      = int(refs_count_row["c"]) if refs_count_row else 0
    referral_bonus_sum = float(refs_bonus_row["s"]) if refs_bonus_row else 0.0

    expires_at   = (sub["expires_at"] if sub else None) or (active_key["expires_at"] if active_key else None)
    active_value = bool(sub and sub["status"] == "active")
    devices_count = int(sub["devices_count"]) if sub else 1
    auto_renew    = bool(sub and int(sub["auto_renew"] or 0) == 1)
    active_key_link  = active_key["vless_link"] if active_key else None
    active_key_email = active_key["email"]      if active_key else None
    active_sub_link  = user_facing_subscription_link(user_id) if active_key else None

    keys_list = []
    for row in all_keys:
        uid = int(row["user_id"])
        sub_link = user_facing_subscription_link(uid) if int(row["is_active"] or 0) else ""
        keys_list.append({
            "id":           int(row["id"]),
            "email":        row["email"],
            "name":         row["email"],
            "key_name":     row["email"],
            "vless_link":   row["vless_link"],
            "access_key":   row["vless_link"],
            "key":          row["vless_link"],
            "subscription_url": sub_link,
            "expires_at":   row["expires_at"],
            "created_at":   row["created_at"],
            "is_active":    bool(int(row["is_active"] or 0)),
            "instructions": INSTALL_INSTRUCTION,
        })
    return {
        "ok": True,
        "user": {
            "id":         int(user["user_id"]),
            "telegram_id":int(user["user_id"]),
            "username":   user["username"] or "",
            "first_name": user["first_name"] or "",
            "last_name":  user["last_name"] or "",
            "trial_used": int(user["trial_used"] or 0),
            "name":       " ".join(filter(None, [user["first_name"] or "", user["last_name"] or ""])) or user["username"] or "Пользователь",
            "full_name":  " ".join(filter(None, [user["first_name"] or "", user["last_name"] or ""])) or user["username"] or "Пользователь",
            "balance":    float(user["balance"] or 0),
        },
        "subscription": {
            "active":          active_value,
            "is_active":       active_value,
            "tariff_id":       sub["tariff_id"]       if sub else None,
            "devices_count":   devices_count,
            "status":          sub["status"]           if sub else "inactive",
            "expires_at":      expires_at,
            "end_date":        expires_at,
            "valid_until":     expires_at,
            "active_until":    expires_at,
            "auto_renew":      auto_renew,
            "autorenew":       auto_renew,
            "is_auto_renew":   auto_renew,
            "payment_method":  sub["payment_method"]  if sub else None,
        },
        "current_subscription": {
            "active":         active_value,
            "is_active":      active_value,
            "tariff_id":      sub["tariff_id"]       if sub else None,
            "devices_count":  devices_count,
            "status":         sub["status"]           if sub else "inactive",
            "expires_at":     expires_at,
            "auto_renew":     auto_renew,
            "payment_method": sub["payment_method"]  if sub else None,
        },
        "keys": {
            "active_key":       active_key_link,
            "active_key_email": active_key_email,
            "vless_link":       active_key_link,
            "key":              active_key_link,
            "small_vless_link": active_key_link,
            "subscription_url": active_sub_link,
            "items":            keys_list,
            "list":             keys_list,
        },
        "subscription_url":       active_sub_link,
        "subscription_expires":   expires_at,
        "my_keys":  keys_list,
        "referrals": {
            "count": refs_count,
            "bonus": referral_bonus_sum,
            "bonus_rub": referral_bonus_sum,
            "reward_rub": CFG.referral_bonus,
        },
        "balance": float(user["balance"] or 0),
        "referral_reward_rub": CFG.referral_bonus,
        "support":  {"username": CFG.support_username},
    }


# =============================================================================
# KEYBOARDS
# =============================================================================

def mini_app_inline_button(text: str = "📱 Открыть Mini App") -> InlineKeyboardButton:
    return InlineKeyboardButton(text=text, web_app=WebAppInfo(url=CFG.mini_app_url))


def mini_app_setup_button(text: str = "📲 Установка и настройка") -> InlineKeyboardButton:
    url = CFG.mini_app_url.rstrip("/") + "/?tgWebAppStartParam=setup"
    return InlineKeyboardButton(text=text, web_app=WebAppInfo(url=url))


def sbp_payment_markup(payment_url: str, button_text: str = "💳 Оплатить через СБП") -> InlineKeyboardMarkup:
    """Обычная url-кнопка (не web_app): pay.platega.io нельзя открывать внутри Mini App iframe."""
    return InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text=button_text, url=payment_url)]]
    )


def sbp_payment_hint(payment_url: str) -> str:
    """Текст со ссылкой и подсказкой для Telegram in-app browser на телефоне."""
    safe_href = html_lib.escape(payment_url, quote=True)
    safe_text = html_lib.escape(payment_url)
    return (
        f"🔗 <a href=\"{safe_href}\">Открыть оплату</a>\n"
        f"<code>{safe_text}</code>\n\n"
        "Если страница в Telegram не грузится — откройте ссылку во внешнем браузере "
        "(⋮ → «Открыть в…» / Safari / Chrome)."
    )


def trial_success_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [mini_app_setup_button()],
        [InlineKeyboardButton(text="📖 Какой профиль?", callback_data="profile_hint")],
        [InlineKeyboardButton(text="🔧 Не работает?", callback_data="vpn_not_working")],
    ])


def referral_link_for_user(user_row) -> str:
    code = (user_row["referral_code"] or "").strip()
    return f"https://t.me/{CFG.bot_username}?start={code}" if code else ""


def referral_share_text(ref_link: str) -> str:
    return ref_contest.referral_share_text(ref_link, CFG.referral_bonus)


def referrals_inline_keyboard(ref_link: str) -> InlineKeyboardMarkup:
    share_url = (
        "https://t.me/share/url?url="
        + urllib.parse.quote(ref_link)
        + "&text="
        + urllib.parse.quote(referral_share_text(ref_link))
    )
    rows = [
        [InlineKeyboardButton(text="📤 Поделиться ссылкой", url=share_url)],
        [
            InlineKeyboardButton(text="📋 Скопировать", callback_data="copy_ref_link"),
            InlineKeyboardButton(text="💳 Пополнить", callback_data="topup_menu"),
        ],
        [mini_app_inline_button("📱 Открыть Mini App")],
    ]
    if ref_contest.is_contest_active():
        rows.insert(1, [InlineKeyboardButton(text="📋 Правила марафона", callback_data="referral_contest_rules")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


async def send_referral_marathon_photo(
    target: Union[types.Message, Bot],
    chat_id: int,
    caption: str,
    reply_markup: Optional[InlineKeyboardMarkup] = None,
    follow_up_text: Optional[str] = None,
) -> None:
    photo = ref_contest.PHOTO_PATH
    photo_sent = False
    if photo.is_file():
        photo_file = FSInputFile(str(photo))
        if isinstance(target, Bot):
            await target.send_photo(chat_id, photo_file, caption=caption, parse_mode="HTML", reply_markup=reply_markup)
        else:
            await target.answer_photo(photo_file, caption=caption, parse_mode="HTML", reply_markup=reply_markup)
        photo_sent = True
    if not photo_sent:
        if isinstance(target, Bot):
            await target.send_message(chat_id, caption, parse_mode="HTML", reply_markup=reply_markup)
        else:
            await target.answer(caption, parse_mode="HTML", reply_markup=reply_markup)
    if follow_up_text:
        if isinstance(target, Bot):
            await target.send_message(chat_id, follow_up_text, parse_mode="HTML", disable_web_page_preview=True)
        else:
            await target.answer(follow_up_text, parse_mode="HTML", disable_web_page_preview=True)


def profile_inline_keyboard(*, sub_active: bool) -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(text="👥 Пригласить друга", callback_data="open_referrals")],
        [InlineKeyboardButton(text="💳 Пополнить баланс", callback_data="topup_menu")],
        [mini_app_inline_button()],
    ]
    if sub_active:
        rows.append([InlineKeyboardButton(text="⚡ Быстрое подключение", callback_data="quick_connect")])
    else:
        rows.append([InlineKeyboardButton(text="📦 Купить тариф", callback_data="open_tariffs")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def help_inline_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📖 Профили VPN", callback_data="profile_hint")],
        [InlineKeyboardButton(text="🔧 VPN не работает", callback_data="vpn_not_working")],
        [InlineKeyboardButton(text="👥 Реферальная программа", callback_data="open_referrals")],
        [mini_app_inline_button()],
        [InlineKeyboardButton(text="💬 Написать в поддержку", url=f"https://t.me/{CFG.support_username}")],
    ])


def quick_connect_keyboard(active: bool, user_id: int | None = None) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    if active and user_id:
        sub_url = user_facing_subscription_link(user_id)
        if sub_url:
            rows.append([
                InlineKeyboardButton(
                    text="Добавить в Happ",
                    url=subscription_import_https_url(sub_url, "happ"),
                ),
                InlineKeyboardButton(
                    text="Добавить в INCY",
                    url=subscription_import_https_url(sub_url, "incy"),
                ),
            ])
            rows.append([InlineKeyboardButton(text="📱 Другое устройство", callback_data="add_other_device")])
    rows.append([mini_app_setup_button("📲 Установка и настройка")])
    rows.append([InlineKeyboardButton(text="📖 Какой профиль?", callback_data="profile_hint")])
    if active:
        rows.append([InlineKeyboardButton(text="🔧 Не работает?", callback_data="vpn_not_working")])
    else:
        rows.append([InlineKeyboardButton(text="📦 Купить тариф", callback_data="open_tariffs")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def other_device_keyboard(user_id: int) -> InlineKeyboardMarkup:
    sub_url = user_facing_subscription_link(user_id)
    rows: list[list[InlineKeyboardButton]] = []
    if sub_url:
        rows.append([
            InlineKeyboardButton(
                text="Добавить в Happ",
                url=subscription_import_https_url(sub_url, "happ"),
            ),
            InlineKeyboardButton(
                text="Добавить в INCY",
                url=subscription_import_https_url(sub_url, "incy"),
            ),
        ])
    rows.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="quick_connect")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def main_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="⚡ Быстрое подключение")],
        [KeyboardButton(text="📦 Тарифы"), KeyboardButton(text="👤 Профиль")],
        [KeyboardButton(text="📱 Mini App"), KeyboardButton(text="👥 Рефералы")],
        [KeyboardButton(text="💳 Пополнить"), KeyboardButton(text="🆘 Помощь")],
        [KeyboardButton(text="🎁 Пробный период")],
    ], resize_keyboard=True)


def tariff_keyboard() -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(
            text=f"{t['emoji']} {t['name']} — {rub(t['price'])}",
            callback_data=f"select_tariff_{tid}",
        )]
        for tid, t in TARIFFS.items()
        if tid != "trial"
    ]
    rows.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="back_main")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def tariff_payment_keyboard(tariff_id: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💰 Оплатить с баланса",     callback_data=f"tariff_balance_{tariff_id}")],
        [InlineKeyboardButton(text="💳 Оплатить через СБП",     callback_data=f"tariff_sbp_{tariff_id}")],
        [InlineKeyboardButton(text="🪙 Оплатить криптовалютой", callback_data=f"tariff_crypto_{tariff_id}")],
        [InlineKeyboardButton(text="⬅️ Назад",                  callback_data="back_tariffs")],
    ])


def topup_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💳 СБП",          callback_data="pay_sbp")],
        [InlineKeyboardButton(text="💰 Криптовалюта", callback_data="pay_crypto")],
        [InlineKeyboardButton(text="⬅️ Назад",        callback_data="back_main")],
    ])


def crypto_keyboard(prefix: str = "crypto_topup") -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💵 USDT", callback_data=f"{prefix}_USDT")],
        [InlineKeyboardButton(text="₮ TON",  callback_data=f"{prefix}_TON")],
        [InlineKeyboardButton(text="₿ BTC",  callback_data=f"{prefix}_BTC")],
        [InlineKeyboardButton(text="💎 ETH",  callback_data=f"{prefix}_ETH")],
        [InlineKeyboardButton(text="⬅️ Назад",callback_data="topup_menu")],
    ])


# =============================================================================
# TELEGRAM BOT HANDLERS
# =============================================================================

@dp.message(Command("appss_verify"))
async def cmd_appss_verify(msg: types.Message) -> None:
    code = os.getenv("APPSS_VERIFY_CODE", "appss_f5f76e").strip()
    if code:
        await msg.answer(code)


@dp.message(Command("start"))
async def cmd_start(msg: types.Message) -> None:
    try:
        existed = db.fetchone("SELECT 1 FROM users WHERE user_id = ?", (msg.from_user.id,)) is not None
    except Exception:
        existed = False
    user = get_or_create_user_from_tg(msg.from_user)
    log_user_event(msg.from_user.id, "repeat_start" if existed else "first_start")
    parts = (msg.text or "").split(maxsplit=1)
    if len(parts) > 1:
        ref = parts[1].strip()
        if ref and ref != str(msg.from_user.id):
            owner  = db.fetchone("SELECT user_id FROM users WHERE referral_code = ?", (ref,))
            already = db.fetchone("SELECT id FROM referrals WHERE referred_id = ?", (msg.from_user.id,))
            if owner and int(owner["user_id"]) != msg.from_user.id and not already:
                db.execute(
                    "INSERT INTO referrals (referrer_id, referred_id, bonus) VALUES (?, ?, ?)",
                    (int(owner["user_id"]), msg.from_user.id, 0),
                )
    keys_row = db.fetchone("SELECT COUNT(*) AS c FROM keys WHERE user_id = ? AND is_active = 1", (msg.from_user.id,))
    refs_row = db.fetchone("SELECT COUNT(*) AS c FROM referrals WHERE referrer_id = ?",           (msg.from_user.id,))
    keys_count = int(keys_row["c"]) if keys_row else 0
    refs_count = int(refs_row["c"]) if refs_row else 0
    sub_row = db.fetchone(
        "SELECT expires_at FROM subscriptions WHERE user_id = ? AND status = 'active'",
        (msg.from_user.id,),
    )
    sub_hint = ""
    if sub_row and sub_row["expires_at"]:
        sub_hint = f"\n📅 Подписка до: <b>{fmt_dt(sub_row['expires_at'])}</b>"
    await msg.answer(
        f"✈️ <b>Добро пожаловать, {safe_name(msg.from_user)}!</b>\n"
        f"{'─' * 22}\n\n"
        f"💰 Баланс: <b>{rub(user['balance'])}</b>"
        f"{sub_hint}\n"
        f"👥 Друзей приглашено: <b>{refs_count}</b>\n"
        f"🎁 Реферальный бонус: <b>{rub(CFG.referral_bonus)}</b> на баланс за друга\n\n"
        "🌊 <b>Triton VPN</b> — быстрый и надёжный.\n"
        "👇 Нажмите <b>⚡ Быстрое подключение</b>, чтобы начать",
        parse_mode="HTML", reply_markup=main_keyboard(),
    )


@dp.message(F.text == "👤 Профиль")
async def profile_handler(msg: types.Message) -> None:
    get_or_create_user_from_tg(msg.from_user)
    profile = user_stats_payload(msg.from_user.id)
    sub     = profile["subscription"]
    refs    = profile.get("referrals") or {}
    exp_str     = fmt_dt(sub["expires_at"]) if sub["expires_at"] else "—"
    status_icon = "🟢" if sub["active"] else "🔴"
    status_text = "Активна" if sub["active"] else "Неактивна"
    renew_icon  = "✅" if sub["auto_renew"] else "❌"
    refs_count  = int(refs.get("count") or 0)
    refs_earned = float(refs.get("bonus_rub") or refs.get("bonus") or 0)
    await msg.answer(
        "👤 <b>Ваш профиль</b>\n"
        f"{'─' * 22}\n\n"
        f"🆔 ID: <code>{msg.from_user.id}</code>\n"
        f"💰 Баланс: <b>{rub(profile['user']['balance'])}</b>\n"
        f"👥 Приглашено друзей: <b>{refs_count}</b>\n"
        f"💎 Заработано с рефералов: <b>{rub(refs_earned)}</b>\n\n"
        f"{status_icon} Подписка: <b>{status_text}</b>\n"
        f"📅 Действует до: <b>{exp_str}</b>\n"
        f"🔄 Автопродление: {renew_icon}\n"
        f"📱 Устройств: <b>{sub['devices_count']}</b>",
        parse_mode="HTML",
        reply_markup=profile_inline_keyboard(sub_active=bool(sub["active"])),
    )


@dp.message(F.text == "📦 Тарифы")
async def tariffs_handler(msg: types.Message) -> None:
    lines = [f"💎 <b>Тарифы Triton VPN</b>\n{'─' * 22}\n"]
    for t in TARIFFS.values():
        lines.append(
            f"{t['emoji']} <b>{t['name']}</b>\n"
            f"   💰 {rub(t['price'])} • 🗓 {t['days']} дней • 📱 {CFG.vpn_max_devices} устр. • 🚀 безлимит\n"
        )
    lines.append(f"🎁 <i>Приглашайте друзей — {rub(CFG.referral_bonus)} на баланс за каждого!</i>")
    await msg.answer("\n".join(lines), parse_mode="HTML", reply_markup=tariff_keyboard())


# ============================================================
# TRIAL: единая функция выдачи пробного периода.
# Использует issue_key_for_user — она сама решает: продлить
# существующий ключ или создать новый. subscription_end
# обновляется через CASE WHEN — не откатывая на более раннюю дату.
# ============================================================
def issue_trial_for_user(user_id, source: str = "unknown"):
    """
    Возвращает (email, vless_link, subscription_url, new_exp)
    или (None, None, None, None) при ошибке.
    НЕ проверяет trial_used — это ответственность вызывающего кода.
    """
    logger.info("issue_trial_for_user called: user_id=%r type=%s", user_id, type(user_id).__name__)
    try:
        user_id = int(user_id)
    except (TypeError, ValueError) as e:
        logger.error("issue_trial_for_user: cannot convert user_id to int: %r (%s)", user_id, e)
        return None, None, None, None
    email, vless_link, subscription_url, new_exp = issue_key_for_user(user_id, "trial")
    if not vless_link or not new_exp:
        return None, None, None, None

    new_exp_iso = new_exp.isoformat()

    db.execute(
        "UPDATE users SET trial_used = 1, "
        "subscription_end = CASE "
        "  WHEN subscription_end IS NULL OR subscription_end < ? THEN ? "
        "  ELSE subscription_end "
        "END "
        "WHERE user_id = ?",
        (new_exp_iso, new_exp_iso, user_id),
    )

    db.execute(
        "INSERT OR REPLACE INTO subscriptions "
        "(user_id, tariff_id, devices_count, status, expires_at, auto_renew, payment_method, updated_at) "
        "VALUES (?, 'trial', 1, 'active', ?, 0, 'trial', CURRENT_TIMESTAMP)",
        (user_id, new_exp_iso),
    )

    db.execute(
        "INSERT INTO trial_events (user_id, source, expires_at) VALUES (?, ?, ?)",
        (user_id, (source or "unknown").strip(), new_exp_iso),
    )

    return email, vless_link, subscription_url, new_exp


@dp.message(F.text == "🎁 Пробный период")
async def trial_handler(msg: types.Message) -> None:
    user = get_or_create_user_from_tg(msg.from_user)
    if int(user["trial_used"] or 0) == 1:
        await msg.answer(
            "❌ <b>Пробный период уже использован.</b>\n\n"
            "Оформите подписку или приглашайте друзей — "
            f"за каждого оплатившего друга на баланс {rub(CFG.referral_bonus)}.",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="📦 Купить тариф", callback_data="open_tariffs")],
                [InlineKeyboardButton(text="👥 Реферальная программа", callback_data="open_referrals")],
            ]),
        )
        return
    email, vless_link, subscription_url, exp = issue_trial_for_user(msg.from_user.id, source="telegram_button")
    if not vless_link or not exp:
        await msg.answer("⚠️ Не удалось активировать пробный период. Напишите в поддержку.")
        return
    key_display = user_facing_subscription_link(msg.from_user.id)
    await msg.answer(
        "🎉 <b>Пробный доступ активирован!</b>\n\n"
        f"⏳ <b>Срок:</b> {CFG.trial_days} дня\n"
        f"📅 <b>До:</b> {exp.strftime('%d.%m.%Y %H:%M')}\n\n"
        f"🔗 <b>Ссылка подписки:</b>\n<code>{key_display}</code>\n\n"
        f"{QUICK_CONNECT_STEPS}",
        parse_mode="HTML",
        reply_markup=trial_success_keyboard(),
    )
    schedule_trial_promo_welcome(msg.from_user.id, msg.from_user.first_name)


PROMO_99_AMOUNT = 99
PROMO_99_TARIFF = "1month"
PROMO_99_CODE = "START99"


# =============================================================================
# BROADCAST: callback-активация триала из рассылки (2026-04-22)
# =============================================================================
@dp.callback_query(F.data == "promo99_buy")
async def promo99_buy_handler(cb: types.CallbackQuery) -> None:
    """Акция: Старт 1 месяц за 99 ₽ из рассылки."""
    log_user_event(cb.from_user.id, "promo99_buy_click")
    tariff = TARIFFS.get(PROMO_99_TARIFF)
    if not tariff:
        await cb.answer("Тариф недоступен", show_alert=True)
        return
    if not acquire_purchase_lock(cb.from_user.id, PROMO_99_TARIFF):
        await cb.answer("⏳ Платёж уже создаётся", show_alert=True)
        return
    try:
        order_id = f"promo99_{PROMO_99_TARIFF}_{cb.from_user.id}_{int(now().timestamp())}"
        payment_result = await platega_client.create_payment(
            amount=PROMO_99_AMOUNT,
            description=f"Акция TritonVPN: {tariff['name']} за {PROMO_99_AMOUNT}₽ user {cb.from_user.id}",
            user_id=cb.from_user.id,
            order_id=order_id,
            extra_payload={
                "user_id": cb.from_user.id,
                "tariff_id": PROMO_99_TARIFF,
                "type": "tariff_purchase",
                "order_id": order_id,
                "devices_count": 1,
                "auto_renew": 0,
                "payment_method": "sbp",
                "promo_code": PROMO_99_CODE,
            },
            payment_method="sbp",
        )
        if not payment_result.get("success"):
            await cb.message.answer(
                f"❌ Ошибка создания платежа:\n<code>{payment_result.get('error')}</code>",
                parse_mode="HTML",
            )
            await cb.answer()
            return
        payment_url = payment_result.get("payment_url")
        payment_id = payment_result.get("payment_id")
        if not payment_url:
            await cb.message.answer("❌ Platega не вернула ссылку на оплату.")
            await cb.answer()
            return
        db.execute(
            "INSERT OR IGNORE INTO tariff_orders (order_id, user_id, tariff_id, payment_method, status, devices_count, auto_renew_enabled) VALUES (?, ?, ?, 'sbp', 'pending', 1, 0)",
            (order_id, cb.from_user.id, PROMO_99_TARIFF),
        )
        if not db.fetchone("SELECT id FROM payments WHERE order_id = ? OR payment_id = ?", (order_id, payment_id)):
            db.execute(
                "INSERT INTO payments (user_id, amount, method, status, order_id, payment_id, created_at, payload_json, tariff_id, devices_count, auto_renew_enabled) VALUES (?, ?, 'sbp_tariff', 'pending', ?, ?, ?, ?, ?, 1, 0)",
                (
                    cb.from_user.id,
                    PROMO_99_AMOUNT,
                    order_id,
                    payment_id,
                    now().isoformat(),
                    json.dumps({"source": "promo99_broadcast", "promo_code": PROMO_99_CODE}, ensure_ascii=False),
                    PROMO_99_TARIFF,
                ),
            )
        await cb.message.answer(
            "🔥 <b>Акция: Старт за 99 ₽</b>\n\n"
            f"📅 <b>1 месяц</b> · полная скорость · 3 режима\n"
            f"💰 К оплате: <b>{PROMO_99_AMOUNT} ₽</b> <s>129 ₽</s>\n\n"
            "Нажмите кнопку ниже — оплата через СБП.\n\n"
            f"{sbp_payment_hint(payment_url)}",
            parse_mode="HTML",
            disable_web_page_preview=True,
            reply_markup=sbp_payment_markup(payment_url, "💳 Оплатить 99 ₽"),
        )
        await cb.answer()
    finally:
        release_purchase_lock(cb.from_user.id)


@dp.callback_query(F.data == "claim_trial_broadcast")
async def claim_trial_broadcast_handler(cb: types.CallbackQuery) -> None:
    """Активация триала по inline-кнопке из рассылочного сообщения."""
    log_user_event(cb.from_user.id, "claim_trial_click", "broadcast")
    await cb.answer()  # убираем спиннер с кнопки
    user = get_or_create_user_from_tg(cb.from_user)
    if int(user["trial_used"] or 0) == 1:
        try:
            await cb.message.edit_text(
                "❌ <b>Пробный период уже использован.</b>\n\n"
                "Вы можете оформить подписку в главном меню бота.",
                parse_mode="HTML",
            )
        except Exception:
            await cb.message.answer(
                "❌ <b>Пробный период уже использован.</b>", parse_mode="HTML"
            )
        return

    email, vless_link, subscription_url, exp = issue_trial_for_user(cb.from_user.id, source="broadcast")
    if not vless_link or not exp:
        await cb.message.answer("⚠️ Не удалось активировать пробный период. Напишите в поддержку.")
        return
    key_display = user_facing_subscription_link(cb.from_user.id)
    logger.info("broadcast_trial: trial issued for user_id=%s until %s", cb.from_user.id, exp.isoformat())

    # Заменяем рассылочное сообщение на сообщение с ключом — чтобы кнопка исчезла
    try:
        await cb.message.edit_text(
            "🎉 <b>Пробный доступ активирован!</b>\n\n"
            f"⏳ <b>Срок:</b> {CFG.trial_days} дня\n"
            f"📅 <b>До:</b> {exp.strftime('%d.%m.%Y %H:%M')}\n\n"
            f"🔗 <b>Ваша подписка (нажмите чтобы скопировать):</b>\n"
            f"<code>{key_display}</code>\n\n"
            f"{INSTALL_INSTRUCTION}",
            parse_mode="HTML",
            reply_markup=trial_success_keyboard(),
        )
    except Exception:
        # Если edit_text упадёт (напр. сообщение слишком старое), отправим новое
        await cb.message.answer(
            "🎉 <b>Пробный доступ активирован!</b>\n\n"
            f"⏳ <b>Срок:</b> {CFG.trial_days} дня\n"
            f"📅 <b>До:</b> {exp.strftime('%d.%m.%Y %H:%M')}\n\n"
            f"🔗 <b>Ваша подписка (нажмите чтобы скопировать):</b>\n"
            f"<code>{key_display}</code>\n\n"
            f"{INSTALL_INSTRUCTION}",
            parse_mode="HTML",
            reply_markup=trial_success_keyboard(),
        )
    schedule_trial_promo_welcome(cb.from_user.id, cb.from_user.first_name)


async def send_quick_connect(msg: types.Message, user_id: int) -> None:
    active_key = get_active_key(user_id)
    if not active_key:
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📦 Купить тариф", callback_data="open_tariffs")],
            [InlineKeyboardButton(text="🎁 Пробный период", callback_data="claim_trial_menu")],
        ])
        await msg.answer(
            "⚡ <b>Быстрое подключение</b>\n"
            f"{'─' * 22}\n\n"
            "❌ Активной подписки пока нет.\n\n"
            "Оформите тариф или активируйте пробный период — и подключение займёт пару минут.",
            parse_mode="HTML",
            reply_markup=kb,
        )
        return

    exp_dt = parse_dt(active_key["expires_at"])
    countdown = ""
    if exp_dt:
        delta = exp_dt - now()
        if delta.days > 0:
            countdown = f"⏳ Осталось: <b>{delta.days} дн.</b>\n"
        elif delta.total_seconds() > 0:
            hours_left = int(delta.total_seconds() // 3600)
            countdown = f"⚠️ Осталось: <b>менее {hours_left + 1} ч.</b>\n"
        else:
            countdown = "🔴 <b>Подписка истекла</b>\n"

    key_display = user_facing_subscription_link(user_id)
    await msg.answer(
        "⚡ <b>Быстрое подключение</b>\n"
        f"{'─' * 22}\n\n"
        f"🟢 Подписка активна\n"
        f"{countdown}"
        f"📅 До: <b>{fmt_dt(active_key['expires_at'])}</b>\n\n"
        f"🔗 <b>Ссылка подписки</b> (нажмите, чтобы скопировать):\n"
        f"<code>{key_display}</code>\n\n"
        f"{QUICK_CONNECT_STEPS}",
        parse_mode="HTML",
        reply_markup=quick_connect_keyboard(True, user_id),
    )


@dp.callback_query(F.data == "add_other_device")
async def add_other_device_cb(cb: types.CallbackQuery) -> None:
    user_id = cb.from_user.id
    active_key = get_active_key(user_id)
    if not active_key:
        await cb.answer("Нет активной подписки", show_alert=True)
        return
    limit = max(1, int(CFG.vpn_max_devices or 2))
    sub_url = user_facing_subscription_link(user_id)
    await cb.message.answer(
        "📱 <b>Добавить другое устройство</b>\n"
        f"{'─' * 22}\n\n"
        f"На подписку входит <b>{limit} устройства</b> одновременно.\n\n"
        "📦 <b>1.</b> Если приложение ещё не установлено — "
        f"<a href=\"{HAPP_IOS_URL}\">Happ</a> или "
        f"<a href=\"{INCY_IOS_URL}\">INCY</a> "
        "(App Store / Google Play)\n\n"
        "🚀 <b>2.</b> Нажмите кнопку ниже — подписка добавится автоматически\n\n"
        "🛡 <b>3.</b> Включите VPN в приложении\n\n"
        f"🔗 <b>Ссылка подписки:</b>\n<code>{sub_url}</code>",
        parse_mode="HTML",
        disable_web_page_preview=True,
        reply_markup=other_device_keyboard(user_id),
    )
    await cb.answer()


@dp.message(F.text.in_({"⚡ Быстрое подключение", "🔑 Мои ключи"}))
async def quick_connect_handler(msg: types.Message) -> None:
    await send_quick_connect(msg, msg.from_user.id)


@dp.callback_query(F.data == "quick_connect")
async def quick_connect_cb(cb: types.CallbackQuery) -> None:
    await send_quick_connect(cb.message, cb.from_user.id)
    await cb.answer()


@dp.callback_query(F.data == "claim_trial_menu")
async def claim_trial_menu_cb(cb: types.CallbackQuery) -> None:
    log_user_event(cb.from_user.id, "claim_trial_click", "menu")
    user = get_or_create_user_from_tg(cb.from_user)
    if int(user["trial_used"] or 0) == 1:
        await cb.message.answer(
            "❌ <b>Пробный период уже использован.</b>\n\n"
            f"Оформите подписку или приглашайте друзей — "
            f"за каждого оплатившего друга на баланс {rub(CFG.referral_bonus)}.",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="📦 Купить тариф", callback_data="open_tariffs")],
                [InlineKeyboardButton(text="👥 Реферальная программа", callback_data="open_referrals")],
            ]),
        )
        await cb.answer()
        return
    email, vless_link, subscription_url, exp = issue_trial_for_user(cb.from_user.id, source="menu")
    if not vless_link or not exp:
        await cb.message.answer("⚠️ Не удалось активировать пробный период. Напишите в поддержку.")
        await cb.answer()
        return
    key_display = user_facing_subscription_link(cb.from_user.id)
    await cb.message.answer(
        "🎉 <b>Пробный доступ активирован!</b>\n\n"
        f"⏳ <b>Срок:</b> {CFG.trial_days} дня\n"
        f"📅 <b>До:</b> {exp.strftime('%d.%m.%Y %H:%M')}\n\n"
        f"🔗 <b>Ссылка подписки:</b>\n<code>{key_display}</code>\n\n"
        f"{QUICK_CONNECT_STEPS}",
        parse_mode="HTML",
        reply_markup=trial_success_keyboard(),
    )
    await cb.answer()
    schedule_trial_promo_welcome(cb.from_user.id, cb.from_user.first_name)


async def send_referrals_card(target: types.Message, user_id: int) -> None:
    if target.from_user:
        user = get_or_create_user_from_tg(target.from_user)
    else:
        user = db.fetchone("SELECT * FROM users WHERE user_id = ?", (user_id,))
    uid = int(user["user_id"])
    cnt_row = db.fetchone("SELECT COUNT(*) AS c FROM referrals WHERE referrer_id = ?", (uid,))
    bonus_row = db.fetchone(
        "SELECT COALESCE(SUM(bonus), 0) AS s FROM referrals WHERE referrer_id = ?", (uid,)
    )
    count = int(cnt_row["c"]) if cnt_row else 0
    total_bonus = float(bonus_row["s"]) if bonus_row else 0.0
    ref_link = referral_link_for_user(user)
    caption = ref_contest.build_referrals_card_caption(
        referral_bonus_rub=CFG.referral_bonus,
        count=count,
        total_bonus_rub=total_bonus,
        ref_link=ref_link,
    )
    await send_referral_marathon_photo(
        target,
        uid,
        caption,
        reply_markup=referrals_inline_keyboard(ref_link),
    )


@dp.message(F.text == "👥 Рефералы")
async def referrals_handler(msg: types.Message) -> None:
    await send_referrals_card(msg, msg.from_user.id)


@dp.message(Command("referral_contest"))
async def referral_contest_handler(msg: types.Message) -> None:
    user = get_or_create_user_from_tg(msg.from_user)
    await send_referral_marathon_photo(
        msg,
        msg.from_user.id,
        ref_contest.load_rules_text(),
        reply_markup=referrals_inline_keyboard(referral_link_for_user(user)),
        follow_up_text=ref_contest.load_rules_text_full(),
    )


@dp.callback_query(F.data == "open_referrals")
async def open_referrals_cb(cb: types.CallbackQuery) -> None:
    log_user_event(cb.from_user.id, "open_referrals_click")
    await send_referrals_card(cb.message, cb.from_user.id)
    await cb.answer()


@dp.callback_query(F.data == "referral_contest_rules")
async def referral_contest_rules_cb(cb: types.CallbackQuery) -> None:
    user = get_or_create_user_from_tg(cb.from_user)
    await send_referral_marathon_photo(
        cb.message,
        cb.from_user.id,
        ref_contest.load_rules_text(),
        reply_markup=referrals_inline_keyboard(referral_link_for_user(user)),
        follow_up_text=ref_contest.load_rules_text_full(),
    )
    await cb.answer()


@dp.callback_query(F.data == "copy_ref_link")
async def copy_ref_link_cb(cb: types.CallbackQuery) -> None:
    user = get_or_create_user_from_tg(cb.from_user)
    ref_link = referral_link_for_user(user)
    if not ref_link:
        await cb.answer("Ссылка не найдена", show_alert=True)
        return
    await cb.message.answer(
        "📋 <b>Ваша реферальная ссылка</b>\n\n"
        f"<code>{ref_link}</code>\n\n"
        "<i>Нажмите на ссылку, чтобы скопировать.</i>",
        parse_mode="HTML",
    )
    await cb.answer("Ссылка отправлена ↑")


@dp.message(F.text.in_({"💳 Пополнить", "💰 Пополнить"}))
async def topup_handler(msg: types.Message) -> None:
    user = get_or_create_user_from_tg(msg.from_user)
    await msg.answer(
        "💳 <b>Пополнение баланса</b>\n"
        f"{'─' * 22}\n\n"
        f"💰 Текущий баланс: <b>{rub(user['balance'])}</b>\n\n"
        "Выберите способ оплаты 👇",
        parse_mode="HTML",
        reply_markup=topup_keyboard(),
    )


@dp.message(F.text == "📱 Mini App")
async def mini_app_handler(msg: types.Message) -> None:
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [mini_app_inline_button("🚀 Открыть TritonVPN")],
        [
            InlineKeyboardButton(text="⚡ Подключение", callback_data="quick_connect"),
            InlineKeyboardButton(text="👥 Рефералы", callback_data="open_referrals"),
        ],
    ])
    await msg.answer(
        "📱 <b>Mini App TritonVPN</b>\n"
        f"{'─' * 22}\n\n"
        f"Оплата, баланс, рефералы ({rub(CFG.referral_bonus)} за друга), "
        "установка Happ и автопродление — всё в одном приложении.",
        parse_mode="HTML",
        reply_markup=kb,
    )


@dp.message(F.text.in_({"🆘 Помощь", "🆘 Поддержка", "📖 Профили VPN", "🔧 VPN не работает"}))
async def help_handler(msg: types.Message) -> None:
    await msg.answer(
        "🆘 <b>Помощь</b>\n"
        f"{'─' * 22}\n\n"
        f"👨‍💻 Поддержка: @{CFG.support_username}\n"
        "⏰ Ответ обычно до 30 минут\n\n"
        "Выберите тему 👇",
        parse_mode="HTML",
        reply_markup=help_inline_keyboard(),
    )


@dp.callback_query(F.data == "profile_hint")
async def profile_hint_cb(cb: types.CallbackQuery) -> None:
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔧 VPN не работает", callback_data="vpn_not_working")],
        [mini_app_inline_button()],
    ])
    await cb.message.answer(VPN_PROFILE_HINT, parse_mode="HTML", reply_markup=kb)
    await cb.answer()


@dp.callback_query(F.data == "vpn_not_working")
async def vpn_not_working_cb(cb: types.CallbackQuery) -> None:
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📖 Какой профиль?", callback_data="profile_hint")],
        [mini_app_inline_button()],
        [InlineKeyboardButton(text="💬 Написать в поддержку", url=f"https://t.me/{CFG.support_username}")],
    ])
    await cb.message.answer(VPN_TROUBLESHOOT_CHECKLIST, parse_mode="HTML", reply_markup=kb)
    await cb.answer()


@dp.callback_query(F.data == "pay_sbp")
async def sbp_handler(cb: types.CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await cb.message.answer("💳 <b>Оплата через СБП</b>\n\nВведите сумму пополнения.\nМинимум: <b>100₽</b>", parse_mode="HTML")
    await state.set_state(PaymentStates.waiting_amount)
    await state.update_data(payment_method="sbp", payment_purpose="balance")
    await cb.answer()


@dp.callback_query(F.data == "pay_crypto")
async def pay_crypto_handler(cb: types.CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await cb.message.answer("💰 <b>Выберите криптовалюту</b>", parse_mode="HTML", reply_markup=crypto_keyboard("crypto_topup"))
    await cb.answer()


@dp.callback_query(F.data.startswith("crypto_topup_"))
async def crypto_select_handler(cb: types.CallbackQuery, state: FSMContext) -> None:
    asset = cb.data.split("_")[-1].upper()
    await state.clear()
    await state.set_state(PaymentStates.waiting_amount)
    await state.update_data(payment_method="crypto", asset=asset, payment_purpose="balance")
    await cb.message.answer(f"💰 <b>{asset}</b>\nВведите сумму пополнения в рублях.\nМинимум: <b>100₽</b>", parse_mode="HTML")
    await cb.answer()


@dp.message(PaymentStates.waiting_amount)
async def amount_handler(msg: types.Message, state: FSMContext) -> None:
    try:
        amount = float(msg.text.replace("₽", "").replace(",", ".").replace(" ", "").strip())
    except Exception:
        await msg.answer("❌ Введите корректную сумму. Например: <b>500</b>", parse_mode="HTML")
        return
    if amount < 100:
        await msg.answer("❌ Минимальная сумма — <b>100₽</b>.", parse_mode="HTML")
        return
    data    = await state.get_data()
    method  = data.get("payment_method")
    purpose = data.get("payment_purpose", "balance")
    if purpose != "balance":
        await msg.answer("❌ Неверный тип платежа.")
        await state.clear()
        return

    if method == "crypto":
        asset  = data.get("asset", "USDT")
        result = crypto_bot.create_invoice(amount_rub=amount, asset=asset, user_id=msg.from_user.id)
        if not result.get("success"):
            await msg.answer(f"❌ Ошибка создания крипто-счёта: {result.get('error')}")
            return
        db.execute(
            "INSERT OR IGNORE INTO crypto_payments (user_id, invoice_id, amount, asset, status, tariff_id, devices_count, auto_renew_enabled) VALUES (?, ?, ?, ?, 'pending', NULL, 1, 0)",
            (msg.from_user.id, result["invoice_id"], amount, asset),
        )
        if not db.fetchone("SELECT id FROM payments WHERE payment_id = ? OR order_id = ?", (result["invoice_id"], result["invoice_id"])):
            db.execute(
                "INSERT INTO payments (user_id, amount, method, status, order_id, payment_id, created_at, payload_json) VALUES (?, ?, 'crypto', 'pending', ?, ?, ?, ?)",
                (msg.from_user.id, amount, result["invoice_id"], result["invoice_id"], now().isoformat(), json.dumps({"source": "telegram_topup"}, ensure_ascii=False)),
            )
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="💳 Оплатить", url=result["invoice_url"])],
            [InlineKeyboardButton(text="✅ Проверить оплату", callback_data=f"check_crypto_{result['invoice_id']}")],
        ])
        await msg.answer(
            f"🧾 <b>Счёт создан</b>\n\n💰 {rub(amount)} = <b>{result['crypto_amount']} {asset}</b>\n⏱️ Действителен 1 час",
            parse_mode="HTML", reply_markup=keyboard,
        )
        await state.clear()
        return

    if method == "sbp":
        payment_result = await platega_client.create_payment(
            amount=amount,
            description=f"Пополнение баланса VPN (user {msg.from_user.id})",
            user_id=msg.from_user.id,
            extra_payload={"type": "balance_topup", "user_id": msg.from_user.id},
            payment_method="sbp",
        )
        if not payment_result.get("success"):
            await msg.answer(f"❌ Ошибка создания платежа СБП:\n<code>{payment_result.get('error')}</code>", parse_mode="HTML")
            return
        payment_url = payment_result.get("payment_url")
        payment_id  = payment_result.get("payment_id")
        order_id    = payment_result.get("order_id")
        if not payment_url:
            await msg.answer("❌ Platega не вернула ссылку на оплату.")
            return
        if not db.fetchone("SELECT id FROM payments WHERE payment_id = ? OR order_id = ?", (payment_id, order_id)):
            db.execute(
                "INSERT INTO payments (user_id, amount, method, status, order_id, payment_id, created_at, payload_json) VALUES (?, ?, 'sbp', 'pending', ?, ?, ?, ?)",
                (msg.from_user.id, amount, order_id, payment_id, now().isoformat(), json.dumps({"source": "telegram_topup"}, ensure_ascii=False)),
            )
        await msg.answer(
            f"📱 <b>Счёт СБП создан</b>\n\n"
            f"💰 Сумма: <b>{rub(amount)}</b>\n"
            "Нажмите кнопку для оплаты.\n\n"
            f"{sbp_payment_hint(payment_url)}",
            parse_mode="HTML",
            disable_web_page_preview=True,
            reply_markup=sbp_payment_markup(payment_url),
        )
        await state.clear()
        return

    await msg.answer("❌ Не выбран способ оплаты.")
    await state.clear()


@dp.callback_query(F.data.startswith("check_crypto_"))
async def check_crypto_payment_handler(cb: types.CallbackQuery) -> None:
    invoice_id = cb.data.split("_", 2)[-1]
    await cb.message.answer("⏳ Проверяю статус платежа...")
    status = crypto_bot.get_invoice_status(invoice_id)
    if status == "paid":
        ok = await process_crypto_payment(invoice_id)
        row = db.fetchone("SELECT tariff_id FROM crypto_payments WHERE invoice_id = ?", (invoice_id,))
        if ok and row and row["tariff_id"]:
            await cb.message.answer("✅ Оплата прошла. Нажмите <b>⚡ Быстрое подключение</b> в меню.", parse_mode="HTML")
        elif ok:
            await cb.message.answer("✅ Платёж подтверждён.")
        else:
            await cb.message.answer("✅ Платёж уже был обработан ранее.")
    elif status == "active":
        await cb.message.answer("⏳ Платёж ещё не подтверждён. Попробуйте позже.")
    elif status == "expired":
        await cb.message.answer("❌ Срок действия счёта истёк. Создайте новый.")
    else:
        await cb.message.answer("⏳ Статус пока не определён. Попробуйте позже.")
    await cb.answer()


@dp.callback_query(F.data.startswith("select_tariff_"))
async def select_tariff_handler(cb: types.CallbackQuery) -> None:
    tariff_id = cb.data.split("select_tariff_", 1)[1]
    tariff    = TARIFFS.get(tariff_id)
    if not tariff:
        await cb.answer("Тариф не найден", show_alert=True)
        return
    await cb.message.answer(
        f"📦 <b>Выбран тариф</b>\n\n"
        f"{tariff['emoji']} <b>{tariff['name']}</b>\n"
        f"💰 Стоимость: <b>{rub(tariff['price'])}</b>\n"
        f"📅 Срок: <b>{tariff['days']} дней</b>\n"
        f"📦 Трафик: <b>безлимит</b>\n\n"
        f"Выберите способ оплаты:",
        parse_mode="HTML", reply_markup=tariff_payment_keyboard(tariff_id),
    )
    await cb.answer()


@dp.callback_query(F.data.startswith("tariff_sbp_"))
async def tariff_sbp_handler(cb: types.CallbackQuery) -> None:
    tariff_id = cb.data.split("tariff_sbp_", 1)[1]
    tariff    = TARIFFS.get(tariff_id)
    if not tariff:
        await cb.answer("Тариф не найден", show_alert=True)
        return
    if not acquire_purchase_lock(cb.from_user.id, tariff_id):
        await cb.answer("⏳ Платёж уже создаётся", show_alert=True)
        return
    try:
        order_id = f"tariff_{tariff_id}_{cb.from_user.id}_{int(now().timestamp())}"
        payment_result = await platega_client.create_payment(
            amount=tariff["price"],
            description=f"Покупка тарифа {tariff['name']} для user {cb.from_user.id}",
            user_id=cb.from_user.id,
            order_id=order_id,
            extra_payload={
                "user_id": cb.from_user.id,
                "tariff_id": tariff_id,
                "type": "tariff_purchase",
                "order_id": order_id,
                "devices_count": 1,
                "auto_renew": 0,
                "payment_method": "sbp",
            },
            payment_method="sbp",
        )
        if not payment_result.get("success"):
            await cb.message.answer(f"❌ Ошибка создания платежа:\n<code>{payment_result.get('error')}</code>", parse_mode="HTML")
            await cb.answer()
            return
        payment_url = payment_result.get("payment_url")
        payment_id  = payment_result.get("payment_id")
        if not payment_url:
            await cb.message.answer("❌ Platega не вернула ссылку на оплату.")
            await cb.answer()
            return
        db.execute(
            "INSERT OR IGNORE INTO tariff_orders (order_id, user_id, tariff_id, payment_method, status, devices_count, auto_renew_enabled) VALUES (?, ?, ?, 'sbp', 'pending', 1, 0)",
            (order_id, cb.from_user.id, tariff_id),
        )
        if not db.fetchone("SELECT id FROM payments WHERE order_id = ? OR payment_id = ?", (order_id, payment_id)):
            db.execute(
                "INSERT INTO payments (user_id, amount, method, status, order_id, payment_id, created_at, payload_json, tariff_id, devices_count, auto_renew_enabled) VALUES (?, ?, 'sbp_tariff', 'pending', ?, ?, ?, ?, ?, 1, 0)",
                (cb.from_user.id, tariff["price"], order_id, payment_id, now().isoformat(), json.dumps({"source": "telegram_tariff"}, ensure_ascii=False), tariff_id),
            )
        await cb.message.answer(
            f"📦 <b>Оплата тарифа</b>\n\n"
            f"{tariff['emoji']} <b>{tariff['name']}</b>\n"
            f"💰 Стоимость: <b>{rub(tariff['price'])}</b>\n"
            f"📅 Срок: <b>{tariff['days']} дней</b>\n\n"
            "Нажмите кнопку ниже для оплаты.\n\n"
            f"{sbp_payment_hint(payment_url)}",
            parse_mode="HTML",
            disable_web_page_preview=True,
            reply_markup=sbp_payment_markup(payment_url),
        )
        await cb.answer()
    finally:
        release_purchase_lock(cb.from_user.id)


@dp.callback_query(F.data.startswith("tariff_crypto_"))
async def tariff_crypto_handler(cb: types.CallbackQuery) -> None:
    tariff_id = cb.data.split("tariff_crypto_", 1)[1]
    tariff    = TARIFFS.get(tariff_id)
    if not tariff:
        await cb.answer("Тариф не найден", show_alert=True)
        return
    result = crypto_bot.create_invoice(amount_rub=tariff["price"], asset="USDT", user_id=cb.from_user.id)
    if not result.get("success"):
        await cb.message.answer(f"❌ Ошибка создания крипто-счёта: {result.get('error')}")
        await cb.answer()
        return
    db.execute(
        "INSERT OR IGNORE INTO crypto_payments (user_id, invoice_id, amount, asset, status, tariff_id, devices_count, auto_renew_enabled) VALUES (?, ?, ?, 'USDT', 'pending', ?, 1, 0)",
        (cb.from_user.id, result["invoice_id"], tariff["price"], tariff_id),
    )
    if not db.fetchone("SELECT id FROM payments WHERE payment_id = ? OR order_id = ?", (result["invoice_id"], result["invoice_id"])):
        db.execute(
            "INSERT INTO payments (user_id, amount, method, status, order_id, payment_id, created_at, payload_json, tariff_id, devices_count, auto_renew_enabled) VALUES (?, ?, 'crypto_tariff', 'pending', ?, ?, ?, ?, ?, 1, 0)",
            (cb.from_user.id, tariff["price"], result["invoice_id"], result["invoice_id"], now().isoformat(), json.dumps({"source": "telegram_tariff_crypto"}, ensure_ascii=False), tariff_id),
        )
    await cb.message.answer(
        f"📦 <b>Оплата тарифа криптовалютой</b>\n\n"
        f"{tariff['emoji']} <b>{tariff['name']}</b>\n"
        f"💰 Стоимость: <b>{rub(tariff['price'])}</b>\n"
        f"📅 Срок: <b>{tariff['days']} дней</b>\n\n"
        "После оплаты нажмите <b>⚡ Быстрое подключение</b> в меню.",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="💳 Оплатить криптовалютой", url=result["invoice_url"])],
            [InlineKeyboardButton(text="✅ Проверить оплату", callback_data=f"check_crypto_{result['invoice_id']}")],
        ]),
    )
    await cb.answer()


@dp.callback_query(F.data.startswith("tariff_balance_"))
async def tariff_balance_handler(cb: types.CallbackQuery) -> None:
    tariff_id = cb.data.split("tariff_balance_", 1)[1]
    tariff    = TARIFFS.get(tariff_id)
    if not tariff:
        await cb.answer("Тариф не найден", show_alert=True)
        return
    if not acquire_purchase_lock(cb.from_user.id, tariff_id):
        await cb.answer("⏳ Платёж уже обрабатывается", show_alert=True)
        return
    try:
        amount  = float(tariff["price"])
        balance = get_balance(cb.from_user.id)
        if balance < amount:
            await cb.message.answer(
            f"❌ <b>Недостаточно средств на балансе</b>\n\n"
            f"💰 Стоимость тарифа: <b>{rub(amount)}</b>\n"
            f"🏦 Ваш баланс: <b>{rub(balance)}</b>\n\n"
            "Пополните баланс или пригласите друзей — "
            f"за каждого оплатившего друга +{rub(CFG.referral_bonus)}.",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="💳 Пополнить баланс", callback_data="topup_menu")],
                [InlineKeyboardButton(text="👥 Реферальная программа", callback_data="open_referrals")],
            ]),
        )
            await cb.answer()
            return
        ok, new_balance = deduct_balance(cb.from_user.id, amount, "tariff_purchase_balance", f"Оплата тарифа {tariff['name']} с баланса")
        if not ok:
            await cb.message.answer("❌ Не удалось списать средства с баланса.")
            await cb.answer()
            return
        email, vless_link, subscription_url, exp = issue_key_for_user(cb.from_user.id, tariff_id)
        if not vless_link:
            add_balance(cb.from_user.id, amount, "refund", f"Возврат за тариф {tariff['name']}")
            await cb.message.answer("❌ Не удалось создать ключ. Деньги возвращены на баланс.", parse_mode="HTML")
            await cb.answer()
            return
        new_exp  = upsert_subscription(cb.from_user.id, tariff_id, 1, "balance", False)
        await _grant_referral_bonus(cb.from_user.id)
        order_id = f"balance_tariff_{tariff_id}_{cb.from_user.id}_{int(now().timestamp())}"
        db.execute(
            "INSERT INTO payments (user_id, amount, method, status, order_id, payment_id, created_at, completed_at, payload_json, tariff_id, devices_count, auto_renew_enabled) VALUES (?, ?, 'balance_tariff', 'paid', ?, ?, ?, ?, ?, ?, 1, 0)",
            (cb.from_user.id, amount, order_id, order_id, now().isoformat(), now().isoformat(), json.dumps({"source": "telegram_balance_tariff"}, ensure_ascii=False), tariff_id),
        )
        key_display = user_facing_subscription_link(cb.from_user.id)
        await cb.message.answer(
            f"✅ <b>Тариф оплачен с баланса</b>\n\n"
            f"{tariff['emoji']} <b>{tariff['name']}</b>\n"
            f"💸 Списано: <b>{rub(amount)}</b>\n"
            f"💰 Остаток: <b>{rub(new_balance)}</b>\n"
            f"📅 Действует до: <b>{fmt_dt(new_exp)}</b>\n\n"
            f"🔗 <b>Ключ:</b>\n<code>{key_display}</code>\n\n"
            f"{INSTALL_INSTRUCTION}",
            parse_mode="HTML", reply_markup=main_keyboard(),
        )
        await cb.answer("Оплачено с баланса")
    finally:
        release_purchase_lock(cb.from_user.id)


@dp.callback_query(F.data == "back_main")
async def back_main_handler(cb: types.CallbackQuery) -> None:
    await cb.message.answer("Главное меню", reply_markup=main_keyboard())
    await cb.answer()


@dp.callback_query(F.data == "back_tariffs")
async def back_tariffs_handler(cb: types.CallbackQuery) -> None:
    await cb.message.answer("💎 <b>Доступные тарифы</b>", parse_mode="HTML", reply_markup=tariff_keyboard())
    await cb.answer()


@dp.callback_query(F.data == "topup_menu")
async def topup_menu_handler(cb: types.CallbackQuery) -> None:
    user = get_or_create_user_from_tg(cb.from_user)
    await cb.message.answer(
        "💳 <b>Пополнение баланса</b>\n"
        f"{'─' * 22}\n\n"
        f"💰 Текущий баланс: <b>{rub(user['balance'])}</b>\n\n"
        "Выберите способ оплаты 👇",
        parse_mode="HTML",
        reply_markup=topup_keyboard(),
    )
    await cb.answer()


@dp.callback_query(F.data == "open_tariffs")
async def open_tariffs_handler(cb: types.CallbackQuery) -> None:
    log_user_event(cb.from_user.id, "open_tariffs_click")
    lines = ["💎 <b>Доступные тарифы</b>\n─────────────────────\n"]
    for t in TARIFFS.values():
        lines.append(
            f"{t['emoji']} <b>{t['name']}</b>\n"
            f"   💰 {rub(t['price'])} • 🗓 {t['days']} дней • 📱 {CFG.vpn_max_devices} устр. • 🚀 безлимит\n"
        )
    lines.append(f"🎁 <i>Приглашайте друзей — {rub(CFG.referral_bonus)} на баланс за каждого!</i>")
    await cb.message.answer("\n".join(lines), parse_mode="HTML", reply_markup=tariff_keyboard())
    await cb.answer()


# =============================================================================
# WEB API
# =============================================================================

async def api_auth_telegram(request: web.Request) -> web.Response:
    try:
        data      = await request.json()
        init_data = data.get("initData") or data.get("init_data") or ""
        tg_user   = validate_telegram_init_data(init_data, CFG.bot_token)
        if not tg_user:
            return json_response({"ok": False, "error": "invalid_telegram_auth"}, 401)
        user    = get_or_create_user_by_webapp(tg_user)
        token   = create_web_session(int(user["user_id"]))
        payload = user_stats_payload(int(user["user_id"]))
        payload.update({"token": token, "access_token": token, "jwt": token})
        return json_response(payload)
    except Exception as e:
        logger.exception("api_auth_telegram failed")
        return json_response({"ok": False, "error": str(e)}, 500)


async def api_me(request: web.Request) -> web.Response:
    user_id = await auth_required(request)
    if not user_id:
        return json_response({"ok": False, "error": "unauthorized"}, 401)
    return json_response(user_stats_payload(user_id))


async def api_history(request: web.Request) -> web.Response:
    user_id = await auth_required(request)
    if not user_id:
        return json_response({"ok": False, "error": "unauthorized"}, 401)
    rows  = db.fetchall("SELECT id, amount, method, status, created_at, completed_at, tariff_id, devices_count, auto_renew_enabled FROM payments WHERE user_id = ? ORDER BY id DESC LIMIT 100", (user_id,))
    items = []
    for row in rows:
        tid   = row["tariff_id"]
        title = f"Оплата тарифа {TARIFFS.get(tid, {}).get('name', tid)}" if tid else "Платёж"
        items.append({
            "id": int(row["id"]), "amount": float(row["amount"]), "price": float(row["amount"]),
            "method": row["method"], "payment_method": row["method"], "status": row["status"],
            "created_at": row["created_at"], "completed_at": row["completed_at"],
            "date": row["completed_at"] or row["created_at"], "tariff_id": tid,
            "devices_count": int(row["devices_count"] or 1),
            "auto_renew_enabled": bool(int(row["auto_renew_enabled"] or 0)),
            "title": title,
            "plan_name":   TARIFFS.get(tid, {}).get("name") if tid else None,
            "tariff_name": TARIFFS.get(tid, {}).get("name") if tid else None,
        })
    return json_response({"ok": True, "items": items, "payments": items, "history": items})


async def api_plans(request: web.Request) -> web.Response:
    plans = [
        {"id": tid, "plan_id": tid, "tariff_id": tid, "name": t["name"], "title": t["name"],
         "days": t["days"], "duration_days": t["days"], "price": t["price"], "amount": t["price"],
         "emoji": t["emoji"],
         "description": f"До {CFG.vpn_max_devices} устройств одновременно. Безлимитный трафик."}
        for tid, t in TARIFFS.items()
    ]
    return json_response({"ok": True, "plans": plans, "tariffs": plans, "items": plans})


async def api_devices(request: web.Request) -> web.Response:
    user_id = await auth_required(request)
    if not user_id:
        return json_response({"ok": False, "error": "unauthorized"}, 401)
    limit = max(1, int(CFG.vpn_max_devices or 2))
    items = [
        {"id": i + 1, "name": f"Устройство {i + 1}", "status": "available", "max": limit}
        for i in range(limit)
    ]
    return json_response({
        "ok": True,
        "max_devices": limit,
        "devices": items,
        "items": items,
        "connections": items,
    })


async def api_my_keys(request: web.Request) -> web.Response:
    user_id = await auth_required(request)
    if not user_id:
        return json_response({"ok": False, "error": "unauthorized"}, 401)
    items = []
    for row in get_all_keys(user_id):
        sub_link = user_facing_subscription_link(user_id) if int(row["is_active"] or 0) else ""
        items.append({
            "id": int(row["id"]), "email": row["email"], "name": row["email"], "key_name": row["email"],
            "vless_link": row["vless_link"], "access_key": row["vless_link"], "key": row["vless_link"],
            "subscription_url": sub_link,
            "expires_at": row["expires_at"], "created_at": row["created_at"],
            "is_active": bool(int(row["is_active"] or 0)), "instructions": INSTALL_INSTRUCTION,
        })
    return json_response({"ok": True, "keys": items, "items": items, "my_keys": items})


async def api_issue_key(request: web.Request) -> web.Response:
    try:
        auth_header = request.headers.get("Authorization", "").strip()
        if CFG.key_issuer_token and auth_header != f"Bearer {CFG.key_issuer_token}":
            return json_response({"ok": False, "error": "unauthorized"}, 401)
        data    = await request.json()
        user_id = int(data.get("user_id"))
        plan    = str(data.get("plan") or "1month").strip().lower()
        devices = int(data.get("devices") or 1)
        if plan not in TARIFFS:
            return json_response({"ok": False, "error": "invalid_plan"}, 400)
        email, vless_link, subscription_url, exp = issue_key_for_user(user_id, plan)
        if not vless_link:
            return json_response({"ok": False, "error": "key_not_created"}, 500)
        new_exp = upsert_subscription(user_id, plan, max(1, devices), "api_issue", False)
        return json_response({
            "ok": True, "user_id": user_id, "email": email,
            "vless_link": vless_link,
            "subscription_url": user_facing_subscription_link(user_id),
            "expires_at": (new_exp or exp).isoformat() if (new_exp or exp) else None,
            "devices": max(1, devices), "plan": plan,
        })
    except Exception as e:
        logger.exception("api_issue_key failed")
        return json_response({"ok": False, "error": str(e)}, 500)


async def api_trial_disabled(request: web.Request) -> web.Response:
    """Trial endpoint disabled on 2026-04-22 — UI button removed."""
    import logging
    try:
        ua = request.headers.get("User-Agent", "")[:200]
        ip = request.headers.get("X-Forwarded-For") or request.remote or "?"
        logging.warning("BLOCKED trial attempt ip=%s ua=%s", ip, ua)
    except Exception:
        pass
    return web.json_response(
        {"ok": False, "error": "trial_disabled",
         "message": "Пробный период временно недоступен"},
        status=410,
    )


async def api_trial(request: web.Request) -> web.Response:
    """Выдача бесплатного триала из mini app (альтернатива trial_handler в Telegram-боте)"""
    user_id = await auth_required(request)
    if not user_id:
        return json_response({"ok": False, "error": "unauthorized"}, 401)
    try:
        user = db.fetchone("SELECT * FROM users WHERE user_id = ?", (user_id,))
        if not user:
            return json_response({"ok": False, "error": "user_not_found"}, 404)
        if int(user["trial_used"] or 0) == 1:
            return json_response({"ok": False, "error": "trial_already_used",
                                  "message": "Пробный период уже использован"}, 400)
        email, vless_link, subscription_url, exp = issue_trial_for_user(user_id, source="miniapp")
        if not vless_link or not exp:
            logger.error("api_trial: issue_trial_for_user failed for user_id=%s", user_id)
            return json_response({"ok": False, "error": "trial_failed",
                                  "message": "Не удалось активировать пробный период"}, 500)
        try:
            logger.info("api_trial: trial issued for user_id=%s until %s", user_id, exp.isoformat())
        except Exception:
            pass
        user_row = db.fetchone("SELECT first_name FROM users WHERE user_id = ?", (user_id,))
        first_name = user_row["first_name"] if user_row else None
        schedule_trial_promo_welcome(user_id, first_name)
        return json_response({
            "ok": True,
            "trial_days": CFG.trial_days,
            "expires_at": exp.isoformat(),
            "email": email,
            "vless_link": vless_link,
            "subscription_url": user_facing_subscription_link(user_id),
        })
    except Exception as e:
        logger.exception("api_trial failed")
        return json_response({"ok": False, "error": str(e)}, 500)


async def api_subscription_purchase(request: web.Request) -> web.Response:
    user_id = await auth_required(request)
    if not user_id:
        return json_response({"ok": False, "error": "unauthorized"}, 401)
    try:
        data           = await request.json()
        tariff_id      = data.get("tariff_id") or data.get("plan_id")
        devices_count  = int(data.get("devices_count", data.get("devices", 1)))
        payment_method = (data.get("payment_method") or data.get("method") or "sbp").lower()
        auto_renew     = bool(data.get("auto_renew", data.get("auto_renew_enabled", False)))
        promo_code     = str(data.get("promo_code") or "").strip()
        if tariff_id not in TARIFFS:
            return json_response({"ok": False, "error": "tariff_not_found"}, 400)
        if payment_method not in {"sbp", "crypto"}:
            return json_response({"ok": False, "error": "only_sbp_and_crypto_allowed"}, 400)
        if devices_count < 1:
            devices_count = 1
        amount = calculate_tariff_amount(tariff_id, devices_count)
        promo_pct = 0
        if promo_code:
            promo_pct, perr = promo_discount_percent(promo_code, user_id)
            if perr:
                return json_response({"ok": False, "error": perr}, 400)
        if promo_pct:
            amount = round(float(amount) * (100 - promo_pct) / 100.0, 2)
        wheel_pct = consume_wheel_discount(user_id)
        if wheel_pct:
            amount = round(float(amount) * (100 - wheel_pct) / 100.0, 2)

        if payment_method == "crypto":
            asset   = (data.get("asset") or "USDT").upper()
            invoice = crypto_bot.create_invoice(amount_rub=amount, asset=asset, user_id=user_id)
            if not invoice.get("success"):
                return json_response({"ok": False, "error": invoice.get("error", "crypto_invoice_error")}, 400)
            db.execute(
                "INSERT OR IGNORE INTO crypto_payments (user_id, invoice_id, amount, asset, status, tariff_id, devices_count, auto_renew_enabled) VALUES (?, ?, ?, ?, 'pending', ?, ?, ?)",
                (user_id, invoice["invoice_id"], amount, asset, tariff_id, devices_count, 1 if auto_renew else 0),
            )
            if not db.fetchone("SELECT id FROM payments WHERE payment_id = ? OR order_id = ?", (invoice["invoice_id"], invoice["invoice_id"])):
                db.execute(
                    "INSERT INTO payments (user_id, amount, method, status, created_at, tariff_id, devices_count, auto_renew_enabled, order_id, payment_id) VALUES (?, ?, 'crypto_tariff', 'pending', ?, ?, ?, ?, ?, ?)",
                    (user_id, amount, now().isoformat(), tariff_id, devices_count, 1 if auto_renew else 0, invoice["invoice_id"], invoice["invoice_id"]),
                )
            return json_response({"ok": True, "payment_type": "crypto", "invoice_url": invoice["invoice_url"], "invoice_id": invoice["invoice_id"], "amount": amount, "url": invoice["invoice_url"], "payment_url": invoice["invoice_url"], "link": invoice["invoice_url"]})

        order_id       = f"web_sbp_{tariff_id}_{user_id}_{int(now().timestamp())}"
        extra_pl: dict = {
            "type": "tariff_purchase",
            "user_id": user_id,
            "tariff_id": tariff_id,
            "devices_count": devices_count,
            "auto_renew": 1 if auto_renew else 0,
            "payment_method": "sbp",
            "source": "web",
            "order_id": order_id,
        }
        if promo_code and promo_pct:
            extra_pl["promo_code"] = promo_code.upper()
        payment_result = await platega_client.create_payment(
            amount=amount,
            description=f"VPN tariff {tariff_id} user {user_id}",
            user_id=user_id,
            order_id=order_id,
            extra_payload=extra_pl,
            payment_method="sbp",
        )
        if not payment_result.get("success"):
            return json_response({"ok": False, "error": payment_result.get("error", "payment_create_failed")}, 400)
        db.execute(
            "INSERT OR IGNORE INTO tariff_orders (order_id, user_id, tariff_id, payment_method, status, devices_count, auto_renew_enabled) VALUES (?, ?, ?, 'sbp', 'pending', ?, ?)",
            (order_id, user_id, tariff_id, devices_count, 1 if auto_renew else 0),
        )
        pay_payload = {"source": "web", "promo_code": promo_code.upper() if promo_pct else ""}
        if not db.fetchone("SELECT id FROM payments WHERE order_id = ? OR payment_id = ?", (order_id, payment_result.get("payment_id"))):
            db.execute(
                "INSERT INTO payments (user_id, amount, method, status, order_id, payment_id, created_at, payload_json, tariff_id, devices_count, auto_renew_enabled) VALUES (?, ?, 'sbp_tariff', 'pending', ?, ?, ?, ?, ?, ?, ?)",
                (user_id, amount, order_id, payment_result.get("payment_id"), now().isoformat(), json.dumps(pay_payload, ensure_ascii=False), tariff_id, devices_count, 1 if auto_renew else 0),
            )
        return json_response({"ok": True, "payment_type": "sbp", "payment_url": payment_result.get("payment_url"), "url": payment_result.get("payment_url"), "link": payment_result.get("payment_url"), "payment_id": payment_result.get("payment_id"), "order_id": order_id, "amount": amount})
    except Exception as e:
        logger.exception("api_subscription_purchase failed")
        return json_response({"ok": False, "error": str(e)}, 500)


async def api_check_payment(request: web.Request) -> web.Response:
    user_id = await auth_required(request)
    if not user_id:
        return json_response({"ok": False, "error": "unauthorized"}, 401)
    order_id   = request.query.get("order_id", "").strip()
    payment_id = request.query.get("payment_id", "").strip()
    invoice_id = request.query.get("invoice_id", "").strip()
    row = None
    if order_id:
        row = db.fetchone("SELECT * FROM payments WHERE user_id = ? AND order_id = ? ORDER BY id DESC LIMIT 1", (user_id, order_id))
    elif payment_id:
        row = db.fetchone("SELECT * FROM payments WHERE user_id = ? AND payment_id = ? ORDER BY id DESC LIMIT 1", (user_id, payment_id))
    elif invoice_id:
        row = db.fetchone("SELECT * FROM payments WHERE user_id = ? AND (payment_id = ? OR order_id = ?) ORDER BY id DESC LIMIT 1", (user_id, invoice_id, invoice_id))
    if not row:
        return json_response({"ok": False, "error": "payment_not_found"}, 404)
    keys       = get_all_keys(user_id)
    latest_key = keys[0] if keys else None
    vpn_key    = None
    if latest_key and row["status"] == "paid" and row["tariff_id"]:
        vpn_key = {
            "key_name": latest_key["email"], "access_key": latest_key["vless_link"],
            "instructions": INSTALL_INSTRUCTION, "expires_at": latest_key["expires_at"],
            "is_active": bool(int(latest_key["is_active"] or 0)),
        }
    return json_response({"ok": True, "order": {"order_id": row["order_id"], "payment_id": row["payment_id"], "status": row["status"], "method": row["method"], "amount": float(row["amount"]), "tariff_id": row["tariff_id"], "vpn_key": vpn_key}})


async def api_web_link_telegram(request: web.Request) -> web.Response:
    token = parse_bearer_token(request)
    if not token:
        return json_response({"ok": False, "error": "unauthorized"}, 401)
    acc = get_web_auth_account_by_token(token)
    if not acc:
        return json_response({"ok": False, "error": "unauthorized"}, 401)
    account_id = int(acc["account_id"])
    try:
        data = await request.json()
    except Exception:
        return json_response({"ok": False, "error": "invalid_json"}, 400)

    tg_id: Optional[int] = None
    payload_user: Optional[dict] = None
    init_data = str(data.get("init_data") or "").strip()
    if init_data:
        u = validate_telegram_init_data(init_data, CFG.bot_token)
        if u:
            payload_user = u
            tg_id = int(u["id"])
    elif isinstance(data.get("widget"), dict):
        w = data["widget"]
        tg_id = verify_telegram_login_widget(w, CFG.bot_token)
        if tg_id is not None:
            payload_user = {
                "id": tg_id,
                "username": w.get("username") or "",
                "first_name": w.get("first_name") or "",
                "last_name": w.get("last_name") or "",
            }

    if tg_id is None or not payload_user:
        return json_response({"ok": False, "error": "invalid_telegram_proof"}, 400)

    other = db.fetchone(
        "SELECT id FROM web_accounts WHERE telegram_user_id = ? AND id != ?",
        (tg_id, account_id),
    )
    if other:
        return json_response({"ok": False, "error": "telegram_already_linked"}, 409)

    cur_tid = acc["telegram_user_id"]
    if cur_tid is not None and int(cur_tid) != tg_id:
        return json_response({"ok": False, "error": "account_already_linked"}, 409)

    try:
        syn = acc["vpn_user_id"]
        if syn is not None:
            merge_web_vpn_into_telegram(int(syn), tg_id)
        get_or_create_user_by_webapp(payload_user, start_param="")
        db.execute(
            "UPDATE web_accounts SET telegram_user_id = ?, vpn_user_id = NULL WHERE id = ?",
            (tg_id, account_id),
        )
    except Exception as e:
        logger.exception("api_web_link_telegram failed")
        return json_response({"ok": False, "error": str(e)}, 500)
    return json_response({"ok": True, "telegram_user_id": tg_id})


async def api_web_subscription_state(request: web.Request) -> web.Response:
    token = parse_bearer_token(request)
    if not token:
        return json_response({"ok": False, "error": "unauthorized"}, 401)
    row = get_web_auth_account_by_token(token)
    if not row:
        return json_response({"ok": False, "error": "unauthorized"}, 401)

    plans = [
        {"id": tid, "name": t["name"], "days": t["days"], "price": t["price"]}
        for tid, t in TARIFFS.items()
        if tid != "trial"
    ]
    tg = row["telegram_user_id"]
    uid = int(tg) if tg is not None else ensure_web_vpn_user(int(row["account_id"]), row["email"] or "")
    sub = get_subscription(uid)
    active_key = get_active_key(uid)
    expires_at = (sub["expires_at"] if sub else None) or (active_key["expires_at"] if active_key else None)
    active_value = bool(sub and sub["status"] == "active")
    tariff_id = sub["tariff_id"] if sub else None
    sub_payload = {
        "active": active_value,
        "status": (sub["status"] if sub else "inactive"),
        "expires_at": expires_at,
        "tariff_id": tariff_id,
        "tariff_name": TARIFFS[tariff_id]["name"] if tariff_id and tariff_id in TARIFFS else None,
        "devices_count": int(sub["devices_count"]) if sub else 1,
        "vless_link": active_key["vless_link"] if active_key else None,
        "subscription_url": user_facing_subscription_link(uid) if active_key else None,
    }

    return json_response({
        "ok": True,
        "email": row["email"],
        "account_id": int(row["account_id"]),
        "telegram_linked": tg is not None,
        "telegram_user_id": int(tg) if tg is not None else None,
        "vpn_user_id": uid,
        "subscription": sub_payload,
        "plans": plans,
    })


async def api_web_subscription_purchase(request: web.Request) -> web.Response:
    return await api_subscription_purchase(request)


async def api_web_check_payment(request: web.Request) -> web.Response:
    return await api_check_payment(request)


async def api_web_account_bootstrap(request: web.Request) -> web.Response:
    token = parse_bearer_token(request)
    if not token:
        return json_response({"ok": False, "error": "unauthorized"}, 401)
    row = get_web_auth_account_by_token(token)
    if not row:
        return json_response({"ok": False, "error": "unauthorized"}, 401)
    account_id = int(row["account_id"])
    uid = ensure_web_vpn_user(account_id, row["email"] or "")
    try:
        data = await request.json()
    except Exception:
        data = {}
    ref = str(data.get("referral_code") or "").strip().upper()
    if ref:
        owner = db.fetchone("SELECT user_id FROM users WHERE referral_code = ?", (ref,))
        already = db.fetchone("SELECT id FROM referrals WHERE referred_id = ?", (uid,))
        if owner and int(owner["user_id"]) != uid and not already:
            db.execute(
                "INSERT INTO referrals (referrer_id, referred_id, bonus) VALUES (?, ?, 0)",
                (int(owner["user_id"]), uid),
            )
    return json_response({"ok": True, "vpn_user_id": uid})


async def api_web_referrals_state(request: web.Request) -> web.Response:
    token = parse_bearer_token(request)
    if not token:
        return json_response({"ok": False, "error": "unauthorized"}, 401)
    row = get_web_auth_account_by_token(token)
    if not row:
        return json_response({"ok": False, "error": "unauthorized"}, 401)
    uid = int(row["telegram_user_id"]) if row["telegram_user_id"] is not None else ensure_web_vpn_user(
        int(row["account_id"]), row["email"] or ""
    )
    u = db.fetchone("SELECT referral_code FROM users WHERE user_id = ?", (uid,))
    code = (u["referral_code"] or "") if u else ""
    cnt_row = db.fetchone("SELECT COUNT(*) AS c FROM referrals WHERE referrer_id = ?", (uid,))
    bonus_row = db.fetchone("SELECT COALESCE(SUM(bonus), 0) AS s FROM referrals WHERE referrer_id = ?", (uid,))
    base = CFG.public_base_url.rstrip("/")
    web_link = f"{base}/register.html?ref={code}" if code else ""
    bonus_sum = float(bonus_row["s"]) if bonus_row else 0.0
    return json_response({
        "ok": True,
        "count": int(cnt_row["c"]) if cnt_row else 0,
        "bonus": bonus_sum,
        "bonus_rub": bonus_sum,
        "reward_rub": CFG.referral_bonus,
        "referral_code": code,
        "telegram_bot_link": f"https://t.me/{CFG.bot_username}?start={code}" if code else "",
        "web_register_link": web_link,
    })


async def api_web_promo_check(request: web.Request) -> web.Response:
    token = parse_bearer_token(request)
    if not token:
        return json_response({"ok": False, "error": "unauthorized"}, 401)
    row = get_web_auth_account_by_token(token)
    if not row:
        return json_response({"ok": False, "error": "unauthorized"}, 401)
    uid = int(row["telegram_user_id"]) if row["telegram_user_id"] is not None else ensure_web_vpn_user(
        int(row["account_id"]), row["email"] or ""
    )
    code = request.query.get("code", "").strip()
    pct, err = promo_discount_percent(code, uid)
    if err:
        return json_response({"ok": False, "error": err, "valid": False})
    return json_response({"ok": True, "valid": True, "percent_off": pct})


async def api_subscription_auto_renew(request: web.Request) -> web.Response:
    user_id = await auth_required(request)
    if not user_id:
        return json_response({"ok": False, "error": "unauthorized"}, 401)
    try:
        data    = await request.json()
        enabled = bool(data.get("enabled", data.get("auto_renew", False)))
        sub     = get_subscription(user_id)
        if not sub:
            return json_response({"ok": False, "error": "subscription_not_found"}, 404)
        db.execute("UPDATE subscriptions SET auto_renew = ?, updated_at = CURRENT_TIMESTAMP WHERE user_id = ?", (1 if enabled else 0, user_id))
        return json_response({"ok": True, "enabled": enabled, "auto_renew": enabled})
    except Exception as e:
        logger.exception("api_subscription_auto_renew failed")
        return json_response({"ok": False, "error": str(e)}, 500)


async def api_subscription_link(request: web.Request) -> web.Response:
    user_id = await auth_required(request)
    if not user_id:
        return json_response({"ok": False, "error": "unauthorized"}, 401)
    key = get_active_key(user_id)
    if not key:
        return json_response({"ok": False, "error": "no_active_key"}, 404)
    sub_link = user_facing_subscription_link(user_id)
    return json_response({
        "ok": True,
        "vless_link": key["vless_link"],
        "small_vless_link": key["vless_link"],
        "subscription_url": sub_link,
        "key": key["vless_link"],
        "email": key["email"],
        "expires_at": key["expires_at"],
    })


async def api_referrals(request: web.Request) -> web.Response:
    user_id = await auth_required(request)
    if not user_id:
        return json_response({"ok": False, "error": "unauthorized"}, 401)
    user      = db.fetchone("SELECT referral_code FROM users WHERE user_id = ?", (user_id,))
    cnt_row   = db.fetchone("SELECT COUNT(*) AS c FROM referrals WHERE referrer_id = ?",              (user_id,))
    bonus_row = db.fetchone("SELECT COALESCE(SUM(bonus), 0) AS s FROM referrals WHERE referrer_id = ?", (user_id,))
    bonus_sum = float(bonus_row["s"]) if bonus_row else 0.0
    return json_response({
        "ok": True,
        "count": int(cnt_row["c"]) if cnt_row else 0,
        "bonus": bonus_sum,
        "bonus_rub": bonus_sum,
        "reward_rub": CFG.referral_bonus,
        "referral_link": f"https://t.me/{CFG.bot_username}?start={user['referral_code']}",
        **ref_contest.contest_api_fields(CFG.public_base_url),
    })


async def api_wheel_state(request: web.Request) -> web.Response:
    user_id = await auth_required(request)
    if not user_id:
        return json_response({"ok": False, "error": "unauthorized"}, 401)
    try:
        balance = get_balance(user_id)
        payload = wheel.wheel_state_payload(db, user_id, balance)
        payload["pending_discount_pct"] = get_wheel_discount_percent(user_id)
        payload["balance"] = balance
        return json_response(payload)
    except Exception as e:
        logger.exception("api_wheel_state failed")
        return json_response({"ok": False, "error": str(e)}, 500)


async def api_wheel_spin(request: web.Request) -> web.Response:
    user_id = await auth_required(request)
    if not user_id:
        return json_response({"ok": False, "error": "unauthorized"}, 401)
    try:
        can, next_at, block = wheel.can_spin(db, user_id)
        if not can:
            err = block or {"code": "cooldown", "message": "Пока нельзя крутить"}
            err["ok"] = False
            err["next_spin_at"] = next_at
            return json_response(err, 429)
        segment = wheel.pick_segment()
        wheel.log_spin(db, user_id, segment)
        extra = None
        if segment["type"] == "balance":
            new_bal = add_balance(
                user_id, float(segment["value"]), "wheel_bonus",
                f"Колесо фортуны +{int(segment['value'])}₽",
            )
            extra = f"💳 Баланс: {new_bal:.0f} ₽"
        elif segment["type"] == "discount":
            cur_pct = get_wheel_discount_percent(user_id)
            new_pct = max(cur_pct, int(segment["value"]))
            db.execute(
                "UPDATE users SET wheel_discount_pct = ? WHERE user_id = ?",
                (new_pct, user_id),
            )
            extra = f"Скидка {new_pct}% при следующей оплате."
        elif segment["type"] == "days":
            exp = grant_vpn_bonus_days(user_id, int(segment["value"]))
            extra = f"📅 Подписка до: {fmt_dt(exp)}" if exp else None
        next_spin = (datetime.utcnow() + timedelta(hours=wheel.WHEEL_COOLDOWN_HOURS)).isoformat() + "Z"
        return json_response({
            "ok": True,
            "segment_id": segment["id"],
            "segment_index": wheel.segment_index(segment["id"]),
            "label": segment["label"],
            "prize_type": segment["type"],
            "prize_value": int(segment["value"]),
            "message": wheel.prize_message(segment, extra),
            "balance": get_balance(user_id),
            "next_spin_at": next_spin,
            "can_spin": False,
            "pending_discount_pct": get_wheel_discount_percent(user_id),
        })
    except Exception as e:
        logger.exception("api_wheel_spin failed")
        return json_response({"ok": False, "error": str(e)}, 500)


async def fulfill_wheel_paid_spin(user_id: int) -> dict:
    spin = wheel.perform_paid_spin(db, user_id)
    segment = spin["segment"]
    extra = None
    if segment["type"] == "balance":
        new_bal = add_balance(
            user_id, float(segment["value"]), "wheel_bonus",
            f"Колесо фортуны +{int(segment['value'])}₽",
        )
        extra = f"💳 Баланс: {new_bal:.0f} ₽"
    elif segment["type"] == "discount":
        cur_pct = get_wheel_discount_percent(user_id)
        new_pct = max(cur_pct, int(segment["value"]))
        db.execute(
            "UPDATE users SET wheel_discount_pct = ? WHERE user_id = ?",
            (new_pct, user_id),
        )
        extra = f"Скидка {new_pct}% при следующей оплате."
    elif segment["type"] == "days":
        exp = grant_vpn_bonus_days(user_id, int(segment["value"]))
        extra = f"📅 Подписка до: {fmt_dt(exp)}" if exp else None
    return {
        "segment": segment,
        "segment_index": wheel.segment_index(segment["id"]),
        "label": segment["label"],
        "message": wheel.prize_message(segment, extra),
        "prize_type": segment["type"],
        "prize_value": int(segment["value"]),
    }


async def api_wheel_spin_paid(request: web.Request) -> web.Response:
    user_id = await auth_required(request)
    if not user_id:
        return json_response({"ok": False, "error": "unauthorized"}, 401)
    try:
        can_paid, block = wheel.can_paid_spin(db, user_id)
        if not can_paid:
            err = dict(block or {"code": "cannot_paid_spin", "message": "Платный спин недоступен"})
            err["ok"] = False
            return json_response(err, 400)

        price = float(wheel.WHEEL_PAID_SPIN_PRICE)
        order_id = f"wheel_{user_id}_{int(now().timestamp())}"
        payment_result = await platega_client.create_payment(
            amount=price,
            description=f"Колесо фортуны TritonVPN ({int(price)}₽)",
            user_id=user_id,
            order_id=order_id,
            extra_payload={
                "user_id": user_id,
                "order_id": order_id,
                "type": "wheel_paid_spin",
                "payment_method": "sbp",
            },
            payment_method="sbp",
        )
        if not payment_result.get("success"):
            return json_response({
                "ok": False,
                "error": payment_result.get("error", "payment_create_failed"),
            }, 400)

        payment_url = payment_result.get("payment_url")
        payment_id = payment_result.get("payment_id") or order_id
        if not payment_url:
            return json_response({"ok": False, "error": "no_payment_url"}, 400)

        if not db.fetchone("SELECT id FROM payments WHERE order_id = ? OR payment_id = ?", (order_id, payment_id)):
            db.execute(
                "INSERT INTO payments (user_id, amount, method, status, order_id, payment_id, created_at, payload_json) "
                "VALUES (?, ?, 'sbp_wheel', 'pending', ?, ?, ?, ?)",
                (
                    user_id, price, order_id, payment_id, now().isoformat(),
                    json.dumps({"type": "wheel_paid_spin", "source": "miniapp"}, ensure_ascii=False),
                ),
            )

        return json_response({
            "ok": True,
            "payment_type": "sbp",
            "payment_url": payment_url,
            "url": payment_url,
            "link": payment_url,
            "order_id": order_id,
            "payment_id": payment_id,
            "amount": int(price),
            "message": f"Оплатите {int(price)} ₽ через СБП — после оплаты колесо крутится автоматически.",
        })
    except Exception as e:
        logger.exception("api_wheel_spin_paid failed")
        return json_response({"ok": False, "error": str(e)}, 500)


# =============================================================================
# PAYMENT PROCESSING
# =============================================================================

async def process_crypto_payment(invoice_id: str) -> bool:
    row = db.fetchone(
        "SELECT user_id, amount, status, tariff_id, devices_count, auto_renew_enabled FROM crypto_payments WHERE invoice_id = ?",
        (invoice_id,),
    )
    if not row:
        return False
    if row["status"] == "paid":
        return True

    user_id    = int(row["user_id"])
    amount_rub = float(row["amount"])
    tariff_id  = row["tariff_id"]

    if tariff_id:
        # ── Тарифная оплата ─────────────────────────────────────────────────
        tariff = TARIFFS.get(tariff_id)
        if not tariff:
            logger.error("process_crypto_payment: unknown tariff_id=%s", tariff_id)
            return False
        devices_count = int(row["devices_count"] or 1)
        auto_renew    = bool(int(row["auto_renew_enabled"] or 0))

        email, vless_link, sub_url_crypto, _exp = issue_key_for_user(user_id, tariff_id)
        if not vless_link:
            logger.error("process_crypto_payment: issue_key_for_user failed for user_id=%s", user_id)
            return False

        new_exp = upsert_subscription(user_id, tariff_id, devices_count, "crypto", auto_renew)
        await _grant_referral_bonus(user_id)  # реф. бонус за первую оплату друга

        existing = db.fetchone("SELECT id FROM payments WHERE payment_id = ? OR order_id = ?", (invoice_id, invoice_id))
        if not existing:
            db.execute(
                "INSERT INTO payments (user_id, amount, method, status, order_id, payment_id, completed_at, tariff_id, devices_count, auto_renew_enabled, payload_json) VALUES (?, ?, 'crypto_tariff', 'paid', ?, ?, ?, ?, ?, ?, ?)",
                (user_id, amount_rub, invoice_id, invoice_id, now().isoformat(), tariff_id, devices_count, 1 if auto_renew else 0, json.dumps({"source": "crypto_webhook"}, ensure_ascii=False)),
            )
        else:
            db.execute(
                "UPDATE payments SET status='paid', completed_at=?, tariff_id=?, devices_count=?, auto_renew_enabled=?, method='crypto_tariff' WHERE payment_id = ? OR order_id = ?",
                (now().isoformat(), tariff_id, devices_count, 1 if auto_renew else 0, invoice_id, invoice_id),
            )
        db.execute("UPDATE crypto_payments SET status = 'paid' WHERE invoice_id = ?", (invoice_id,))

        try:
            await bot.send_message(
                user_id,
                f"✅ <b>Оплата прошла успешно</b>\n\n"
                f"📦 Тариф: <b>{tariff['name']}</b>\n"
                f"💵 Стоимость: <b>{rub(amount_rub)}</b>\n"
                f"📱 Устройств: <b>{devices_count}</b>\n"
                f"📅 Действует до: <b>{fmt_dt(new_exp)}</b>\n"
                f"🔁 Автопродление: <b>{'включено' if auto_renew else 'выключено'}</b>\n\n"
                f"🔐 Подписка готова — нажмите <b>⚡ Быстрое подключение</b>:\n<code>{vless_link}</code>\n\n"
                f"{INSTALL_INSTRUCTION}",
                parse_mode="HTML", reply_markup=main_keyboard(),
            )
        except Exception:
            logger.exception("Failed to notify user about crypto tariff payment")
        return True

    # ── Пополнение баланса ───────────────────────────────────────────────────
    new_balance = add_balance(user_id, amount_rub, "crypto_deposit", "Пополнение через криптовалюту")
    db.execute("UPDATE crypto_payments SET status = 'paid' WHERE invoice_id = ?", (invoice_id,))
    existing = db.fetchone("SELECT id FROM payments WHERE payment_id = ? OR order_id = ?", (invoice_id, invoice_id))
    if not existing:
        db.execute(
            "INSERT INTO payments (user_id, amount, method, status, order_id, payment_id, completed_at, payload_json) VALUES (?, ?, 'crypto', 'paid', ?, ?, ?, ?)",
            (user_id, amount_rub, invoice_id, invoice_id, now().isoformat(), json.dumps({"source": "crypto_webhook"}, ensure_ascii=False)),
        )
    else:
        db.execute("UPDATE payments SET status='paid', completed_at=?, method='crypto' WHERE payment_id = ? OR order_id = ?", (now().isoformat(), invoice_id, invoice_id))

    try:
        await bot.send_message(
            user_id,
            f"💳 Оплата зачислена.\n\n💵 Сумма: <b>{rub(amount_rub)}</b>\n🏦 Баланс: <b>{rub(new_balance)}</b>",
            parse_mode="HTML", reply_markup=main_keyboard(),
        )
    except Exception:
        logger.exception("Failed to notify user about crypto deposit")
    return True


async def handle_crypto_webhook(request: web.Request) -> web.Response:
    try:
        data        = await request.json()
        payload_raw = data.get("payload")
        payload_obj: dict = {}
        if isinstance(payload_raw, dict):
            payload_obj = payload_raw
        elif isinstance(payload_raw, str):
            try:
                payload_obj = json.loads(payload_raw)
            except Exception:
                payload_obj = {}
        invoice_id = (
            data.get("invoice_id") or data.get("id")
            or payload_obj.get("invoice_id") or payload_obj.get("hash")
        )
        if not invoice_id:
            return web.Response(text="OK")
        if data.get("update_type") == "invoice_paid" or data.get("status") == "paid":
            await process_crypto_payment(str(invoice_id))
        return web.Response(text="OK")
    except Exception:
        logger.exception("Crypto webhook error")
        return web.Response(text="Error")


def _platega_amount(data: dict) -> float:
    details = data.get("paymentDetails") if isinstance(data.get("paymentDetails"), dict) else {}
    raw = data.get("amount") or details.get("amount") or 0
    try:
        return float(raw)
    except (TypeError, ValueError):
        return 0.0


def _platega_meta(data: dict) -> dict:
    payload_data = data.get("payload") or data.get("metadata") or data.get("extra_payload") or {}
    if isinstance(payload_data, str):
        try:
            payload_data = json.loads(payload_data)
        except Exception:
            payload_data = {}
    return payload_data if isinstance(payload_data, dict) else {}


async def fulfill_platega_transaction(data: dict) -> bool:
    """Начисляет тариф/баланс по объекту транзакции Platega (webhook или poll)."""
    transaction_id = str(data.get("id") or data.get("transactionId") or data.get("transaction_id") or "")
    status         = str(data.get("status", "")).upper()
    amount         = _platega_amount(data)
    meta           = _platega_meta(data)
    logger.info("PLATEGA FULFILL META: %s status=%s tx=%s amount=%s", meta, status, transaction_id, amount)
    user_id      = int(meta.get("user_id", 0) or 0)
    payment_type = meta.get("type", "balance_topup")
    order_id     = meta.get("order") or meta.get("order_id")

    if status not in ("CONFIRMED", "PAID") or not user_id:
        return False

    if payment_type == "wheel_paid_spin":
        if db.fetchone(
            "SELECT id FROM payments WHERE (payment_id = ? OR order_id = ?) AND status = 'paid'",
            (transaction_id, order_id),
        ):
            return True

        prize = await fulfill_wheel_paid_spin(user_id)
        payment_row = db.fetchone(
            "SELECT id FROM payments WHERE payment_id = ? OR order_id = ?",
            (transaction_id, order_id),
        )
        if payment_row:
            db.execute(
                "UPDATE payments SET user_id=?, amount=?, method='sbp_wheel', status='paid', completed_at=?, payload_json=? "
                "WHERE payment_id = ? OR order_id = ?",
                (user_id, amount, now().isoformat(), json.dumps(data, ensure_ascii=False), transaction_id, order_id),
            )
        else:
            db.execute(
                "INSERT INTO payments (user_id, amount, method, status, order_id, payment_id, completed_at, payload_json) "
                "VALUES (?, ?, 'sbp_wheel', 'paid', ?, ?, ?, ?)",
                (user_id, amount, order_id, transaction_id, now().isoformat(), json.dumps(data, ensure_ascii=False)),
            )
        try:
            await bot.send_message(
                user_id,
                f"🎡 <b>Колесо фортуны</b>\n\n"
                f"✅ Оплата <b>{rub(amount)}</b> прошла!\n\n"
                f"🎁 <b>{prize['label']}</b>\n\n"
                f"{prize['message']}",
                parse_mode="HTML",
                reply_markup=main_keyboard(),
            )
        except Exception:
            logger.exception("Failed to notify user about wheel payment")
        return True

    if payment_type == "tariff_purchase":
        tariff_id      = resolve_tariff_id_for_order(meta, order_id, transaction_id)
        devices_count  = int(meta.get("devices_count", 1) or 1)
        auto_renew     = bool(int(meta.get("auto_renew", 0) or 0))
        payment_method = meta.get("payment_method", "sbp")
        tariff         = TARIFFS.get(tariff_id) if tariff_id else None
        if not tariff:
            logger.error("fulfill_platega_transaction: unknown tariff order_id=%s meta=%s", order_id, meta)
            return False

        if db.fetchone(
            "SELECT id FROM payments WHERE (payment_id = ? OR order_id = ?) AND status = 'paid'",
            (transaction_id, order_id),
        ):
            return True

        new_exp = upsert_subscription(user_id, tariff_id, devices_count, payment_method, auto_renew)
        if get_active_key(user_id):
            sync_active_key_expiry(user_id, new_exp)
        else:
            _email, vless_link, _sub_url, _exp = issue_key_for_user(user_id, tariff_id)
            if not vless_link:
                logger.error("fulfill_platega_transaction: issue_key_for_user failed for user_id=%s", user_id)
                return False
            sync_active_key_expiry(user_id, new_exp)
        active_key = get_active_key(user_id)
        vless_link = (active_key["vless_link"] if active_key else "") or ""
        await _grant_referral_bonus(user_id)
        promo_c = str(meta.get("promo_code") or "").strip().upper()
        if promo_c:
            record_promo_redemption(user_id, promo_c)

        payment_row = db.fetchone(
            "SELECT id FROM payments WHERE payment_id = ? OR order_id = ?",
            (transaction_id, order_id),
        )
        if payment_row:
            db.execute(
                "UPDATE payments SET user_id=?, amount=?, method=?, status='paid', completed_at=?, tariff_id=?, devices_count=?, auto_renew_enabled=?, payload_json=? WHERE payment_id = ? OR order_id = ?",
                (user_id, amount, f"{payment_method}_tariff", now().isoformat(), tariff_id, devices_count, 1 if auto_renew else 0, json.dumps(data, ensure_ascii=False), transaction_id, order_id),
            )
        else:
            db.execute(
                "INSERT INTO payments (user_id, amount, method, status, order_id, payment_id, completed_at, tariff_id, devices_count, auto_renew_enabled, payload_json) VALUES (?, ?, ?, 'paid', ?, ?, ?, ?, ?, ?, ?)",
                (user_id, amount, f"{payment_method}_tariff", order_id, transaction_id, now().isoformat(), tariff_id, devices_count, 1 if auto_renew else 0, json.dumps(data, ensure_ascii=False)),
            )
        if order_id:
            db.execute("UPDATE tariff_orders SET status = 'done' WHERE order_id = ?", (order_id,))

        try:
            await bot.send_message(
                user_id,
                f"✅ <b>Оплата прошла успешно</b>\n\n"
                f"{tariff['emoji']} <b>{tariff['name']}</b>\n"
                f"💰 Стоимость: <b>{rub(amount)}</b>\n"
                f"📅 Действует до: <b>{fmt_dt(new_exp)}</b>\n"
                f"📦 Устройств: <b>{devices_count}</b>\n"
                f"🔄 Автопродление: <b>{'включено' if auto_renew else 'выключено'}</b>\n\n"
                f"🔗 <b>Подписка готова — «⚡ Быстрое подключение»:</b>\n<code>{vless_link}</code>\n\n"
                f"{INSTALL_INSTRUCTION}",
                parse_mode="HTML", reply_markup=main_keyboard(),
            )
        except Exception:
            logger.exception("Failed to notify user about tariff payment")
        return True

    if db.fetchone("SELECT id FROM payments WHERE payment_id = ? AND status = 'paid'", (transaction_id,)):
        return True
    new_balance = add_balance(user_id, amount, "sbp_deposit", "Пополнение через СБП")
    payment_row = db.fetchone("SELECT id FROM payments WHERE payment_id = ? OR order_id = ?", (transaction_id, order_id))
    if payment_row:
        db.execute(
            "UPDATE payments SET user_id=?, amount=?, method='sbp', status='paid', completed_at=?, payload_json=? WHERE payment_id = ? OR order_id = ?",
            (user_id, amount, now().isoformat(), json.dumps(data, ensure_ascii=False), transaction_id, order_id),
        )
    else:
        db.execute(
            "INSERT INTO payments (user_id, amount, method, status, payment_id, order_id, completed_at, payload_json) VALUES (?, ?, 'sbp', 'paid', ?, ?, ?, ?)",
            (user_id, amount, transaction_id, order_id, now().isoformat(), json.dumps(data, ensure_ascii=False)),
        )
    try:
        await bot.send_message(
            user_id,
            f"✅ <b>Оплата зачислена</b>\n\n💰 Сумма: <b>{rub(amount)}</b>\n💳 Баланс: <b>{rub(new_balance)}</b>",
            parse_mode="HTML", reply_markup=main_keyboard(),
        )
    except Exception:
        logger.exception("Failed to notify user about SBP payment")
    return True


async def handle_platega_webhook(request: web.Request) -> web.Response:
    try:
        incoming_secret = request.headers.get("X-Secret") or request.headers.get("x-secret")
        if CFG.platega_api_key and incoming_secret and incoming_secret != CFG.platega_api_key:
            logger.warning("Platega webhook rejected: X-Secret mismatch")
            return web.Response(status=401, text="Invalid X-Secret")
        data = await request.json()
        logger.info("PLATEGA WEBHOOK RAW keys=%s status=%s id=%s", list(data)[:12], data.get("status"), data.get("id"))
        await fulfill_platega_transaction(data)
        return web.Response(text="OK")
    except Exception:
        logger.exception("Platega webhook error")
        return web.Response(text="Error")


# =============================================================================
# BACKGROUND TASKS
# =============================================================================

async def auto_check_payments() -> None:
    logger.info("Auto-check payments started")
    while True:
        try:
            await asyncio.sleep(30)
            pending = db.fetchall("SELECT invoice_id FROM crypto_payments WHERE status = 'pending'")
            for row in pending:
                status = crypto_bot.get_invoice_status(row["invoice_id"])
                if status == "paid":
                    await process_crypto_payment(row["invoice_id"])
                elif status == "expired":
                    db.execute("UPDATE crypto_payments SET status = 'expired' WHERE invoice_id = ?", (row["invoice_id"],))

            pending_sbp = db.fetchall(
                "SELECT id, payment_id, order_id, created_at FROM payments "
                "WHERE status = 'pending' AND IFNULL(payment_id, '') != ''"
            )
            cutoff = now() - timedelta(hours=48)
            for row in pending_sbp:
                payment_id = str(row["payment_id"] or "")
                info = await platega_client.get_payment_status(payment_id)
                remote_status = str((info or {}).get("status") or "").upper()
                created = parse_dt(row["created_at"])
                if remote_status in ("CONFIRMED", "PAID"):
                    logger.info("Auto-check Platega CONFIRMED payment_id=%s", payment_id)
                    await fulfill_platega_transaction(info or {})
                elif remote_status in ("CANCELED", "CANCELLED", "FAILED", "EXPIRED"):
                    db.execute("UPDATE payments SET status = 'expired' WHERE id = ?", (row["id"],))
                    if row["order_id"]:
                        db.execute(
                            "UPDATE tariff_orders SET status = 'failed' WHERE order_id = ? AND status = 'pending'",
                            (row["order_id"],),
                        )
                elif created and created < cutoff:
                    db.execute("UPDATE payments SET status = 'expired' WHERE id = ? AND status = 'pending'", (row["id"],))
                    if row["order_id"]:
                        db.execute(
                            "UPDATE tariff_orders SET status = 'failed' WHERE order_id = ? AND status = 'pending'",
                            (row["order_id"],),
                        )
        except Exception:
            logger.exception("Auto-check payments loop error")
        await asyncio.sleep(60)


async def auto_disable_expired_keys() -> None:
    logger.info("Expired keys watcher started")
    while True:
        try:
            await asyncio.sleep(60)
            rows = db.fetchall(
                "SELECT id, user_id, email, expires_at, "
                "notified_3days, notified_1day, notified_today, notified_expired "
                "FROM keys WHERE is_active = 1"
            )
            for row in rows:
                exp_dt = parse_dt(row["expires_at"])
                if not exp_dt:
                    continue
                delta      = exp_dt - now()
                hours_left = delta.total_seconds() / 3600
                renew_kb   = InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="🔄 Продлить тариф", callback_data="open_tariffs")]
                ])

                # ── Уведомление за 3 дня ──────────────────────────────────────
                if 47 <= hours_left <= 73 and not int(row["notified_3days"] or 0):
                    try:
                        await bot.send_message(
                            row["user_id"],
                            f"⚠️ <b>Ваш VPN истекает через 3 дня!</b>\n\n"
                            f"📅 Дата окончания: <b>{exp_dt.strftime('%d.%m.%Y %H:%M')}</b>\n\n"
                            f"Успейте продлить подписку, чтобы не потерять доступ к VPN.",
                            parse_mode="HTML", reply_markup=renew_kb,
                        )
                        db.execute("UPDATE keys SET notified_3days = 1 WHERE id = ?", (row["id"],))
                    except Exception:
                        logger.exception("Failed to send 3-day notification to user %s", row["user_id"])

                # ── Уведомление за 1 день ─────────────────────────────────────
                elif 0 < hours_left <= 25 and not int(row["notified_1day"] or 0):
                    try:
                        await bot.send_message(
                            row["user_id"],
                            f"🔔 <b>Ваш VPN истекает завтра!</b>\n\n"
                            f"📅 Дата окончания: <b>{exp_dt.strftime('%d.%m.%Y %H:%M')}</b>\n\n"
                            f"⏰ Осталось меньше суток. Продлите сейчас, чтобы VPN работал без перебоев.",
                            parse_mode="HTML", reply_markup=renew_kb,
                        )
                        db.execute("UPDATE keys SET notified_1day = 1 WHERE id = ?", (row["id"],))
                    except Exception:
                        logger.exception("Failed to send 1-day notification to user %s", row["user_id"])

                # ── Уведомление в день истечения (менее 6 часов) ──────────────
                elif 0 < hours_left <= 6 and not int(row["notified_today"] or 0):
                    try:
                        await bot.send_message(
                            row["user_id"],
                            f"🚨 <b>VPN истекает сегодня!</b>\n\n"
                            f"⏰ Время окончания: <b>{exp_dt.strftime('%d.%m.%Y %H:%M')}</b>\n\n"
                            f"⚡ Продлите прямо сейчас — осталось менее {int(hours_left) + 1} ч.",
                            parse_mode="HTML", reply_markup=renew_kb,
                        )
                        db.execute("UPDATE keys SET notified_today = 1 WHERE id = ?", (row["id"],))
                    except Exception:
                        logger.exception("Failed to send today notification to user %s", row["user_id"])

                # ── Ключ истёк ────────────────────────────────────────────────
                elif exp_dt <= now() and not int(row["notified_expired"] or 0):
                    sub_row = db.fetchone(
                        "SELECT tariff_id FROM subscriptions WHERE user_id = ?",
                        (row["user_id"],),
                    )
                    is_trial_expiry = (
                        sub_row is not None
                        and str(sub_row["tariff_id"] or "") == "trial"
                    )
                    try:
                        xui.disable_client(row["email"])
                    except Exception:
                        logger.exception("Failed to disable client %s in xui", row["email"])
                    db.execute(
                        "UPDATE keys SET is_active = 0, notified_expired = 1 WHERE id = ?",
                        (row["id"],)
                    )
                    db.execute(
                        "UPDATE subscriptions SET status = 'inactive', updated_at = CURRENT_TIMESTAMP WHERE user_id = ?",
                        (row["user_id"],)
                    )
                    if is_trial_expiry:
                        logger.info(
                            "Skip generic expired notify for trial user_id=%s (drip handles winback)",
                            row["user_id"],
                        )
                        continue
                    try:
                        await bot.send_message(
                            row["user_id"],
                            f"⛔ <b>Ваш VPN отключён</b>\n\n"
                            f"📅 Срок действия истёк: <b>{exp_dt.strftime('%d.%m.%Y %H:%M')}</b>\n\n"
                            f"Чтобы снова пользоваться VPN — продлите тариф.",
                            parse_mode="HTML", reply_markup=renew_kb,
                        )
                    except Exception:
                        logger.exception("Failed to notify user %s about expired key", row["user_id"])
        except Exception:
            logger.exception("Expired keys watcher loop error")
        await asyncio.sleep(60)


async def auto_renew_subscriptions() -> None:
    logger.info("Auto-renew watcher started")
    while True:
        try:
            await asyncio.sleep(3600)
            rows = db.fetchall(
                "SELECT * FROM subscriptions WHERE status = 'active' AND auto_renew = 1 AND expires_at IS NOT NULL"
            )
            for row in rows:
                exp = parse_dt(row["expires_at"])
                if not exp:
                    continue
                # Автопродление когда до истечения меньше 24 часов
                if exp <= now() + timedelta(hours=24):
                    user_id   = row["user_id"]
                    tariff_id = row["tariff_id"]
                    devices   = int(row["devices_count"] or 1)
                    if tariff_id not in TARIFFS:
                        continue
                    amount  = calculate_tariff_amount(tariff_id, devices)
                    balance = get_balance(user_id)
                    if balance >= amount:
                        try:
                            deduct_balance(user_id, amount, "auto_renew", f"Автопродление тарифа {tariff_id}")
                            new_exp = upsert_subscription(user_id, tariff_id, devices, "balance", True)
                            issue_key_for_user(user_id, tariff_id)
                            logger.info("Auto-renewed user_id=%s tariff=%s until %s", user_id, tariff_id, new_exp)
                            await bot.send_message(
                                user_id,
                                f"✅ <b>Подписка автоматически продлена!</b>\n\n"
                                f"📦 Тариф: <b>{TARIFFS[tariff_id]['name']}</b>\n"
                                f"💰 Списано: <b>{rub(amount)}</b>\n"
                                f"📅 Действует до: <b>{new_exp.strftime('%d.%m.%Y')}</b>",
                                parse_mode="HTML",
                            )
                        except Exception:
                            logger.exception("Auto-renew failed for user_id=%s", user_id)
                    else:
                        # Недостаточно баланса — уведомляем
                        kb = InlineKeyboardMarkup(inline_keyboard=[
                            [InlineKeyboardButton(text="💰 Пополнить баланс", callback_data="topup_menu")],
                            [InlineKeyboardButton(text="🔄 Продлить тариф",   callback_data="open_tariffs")],
                        ])
                        try:
                            await bot.send_message(
                                user_id,
                                f"⚠️ <b>Не удалось автопродлить подписку</b>\n\n"
                                f"📦 Тариф: <b>{TARIFFS[tariff_id]['name']}</b>\n"
                                f"💰 Нужно: <b>{rub(amount)}</b>, на балансе: <b>{rub(balance)}</b>\n\n"
                                f"Пополните баланс или продлите вручную.",
                                parse_mode="HTML",
                                reply_markup=kb,
                            )
                        except Exception:
                            logger.exception("Failed to notify auto-renew failure for user_id=%s", user_id)
        except Exception:
            logger.exception("Auto-renew watcher loop error")
        await asyncio.sleep(300)


# =============================================================================
# SUBSCRIPTION PROXY (pretty URL → x-ui sub content)
# =============================================================================

async def resolve_user_sub_id(user_id: int) -> str:
    key = get_active_key(user_id)
    if not key:
        return ""
    sub_id = extract_sub_id(row_get(key, "subscription_url", ""))
    if sub_id:
        return sub_id
    inbound = xui._get_inbound()
    if not inbound:
        return ""
    clients = xui._parse_clients(inbound)
    target = next((c for c in clients if c.get("email") == key["email"]), None)
    if not target:
        return ""
    sub_id = (target.get("subId") or target.get("sub_id") or "").strip()
    if sub_id:
        db.execute(
            "UPDATE keys SET subscription_url = ? WHERE user_id = ? AND is_active = 1",
            (xui_subscription_link(sub_id), user_id),
        )
    return sub_id


async def fetch_xui_subscription_body(sub_id: str) -> Optional[bytes]:
    if not sub_id:
        return None
    url = f"http://127.0.0.1:2096/sub/{sub_id}"
    try:
        timeout = ClientTimeout(total=10)
        async with ClientSession(timeout=timeout) as session:
            async with session.get(url) as resp:
                if resp.status == 200:
                    return await resp.read()
                logger.warning("x-ui sub fetch status=%s url=%s", resp.status, url)
    except Exception:
        logger.exception("fetch_xui_subscription_body failed sub_id=%s", sub_id)
    return None


def stable_subscription_body(user_id: int) -> Optional[str]:
    """
    Стабильная подписка из bot.db.
    x-ui :2096/sub рандомизирует sid/spx при каждом запросе — клиенты отваливаются.
    """
    key = get_active_key(user_id)
    if not key:
        return None
    link = (key["vless_link"] or "").strip()
    if not link.startswith("vless://"):
        inbound = xui._get_inbound()
        if inbound:
            clients = xui._parse_clients(inbound)
            client = next((c for c in clients if c.get("email") == key["email"]), None)
            if client:
                link = make_vless_link(client["id"], key["email"])
                db.execute(
                    "UPDATE keys SET vless_link = ? WHERE user_id = ? AND is_active = 1",
                    (link, user_id),
                )
    return format_happ_subscription_body(link) if link else None


async def api_subscription_proxy(request: web.Request) -> web.Response:
    try:
        user_id = int(request.match_info["user_id"])
    except (KeyError, ValueError, TypeError):
        raise web.HTTPNotFound()
    key = get_active_key(user_id)
    if not key:
        try:
            from xui_vless_lookup import lookup_nl_client
            hit = lookup_nl_client(int(user_id))
        except Exception:
            hit = None
        if not hit:
            raise web.HTTPNotFound(text="Subscription not found")
        link = str(hit.get("vless") or "")
        if CFG.subscription_format in ("json", "1", "true", "yes") and link.startswith("vless://"):
            from happ_json_config import build_happ_json_subscription
            payload = build_happ_json_subscription(
                link,
                user_id=user_id,
                email=str(hit.get("email") or ""),
                expires_at=hit.get("expires_at"),
            )
            return web.Response(
                text=json.dumps(payload, ensure_ascii=False),
                content_type="application/json",
                headers=happ_subscription_headers(user_id),
            )
        raise web.HTTPNotFound(text="Subscription not found")

    action = (request.query.get("action") or "").strip().lower()
    app = (request.query.get("app") or "happ").strip().lower()
    if action == "add" and app in ("happ", "incy"):
        sub_url = user_facing_subscription_link(user_id)
        try:
            deep = build_app_deep_link(sub_url, app)  # type: ignore[arg-type]
            html = app_import_redirect_html(deep, app, sub_url=sub_url)  # type: ignore[arg-type]
            return web.Response(text=html, content_type="text/html", charset="utf-8")
        except ValueError as e:
            raise web.HTTPBadRequest(text=str(e))

    link = (row_get(key, "vless_link", "") or "").strip()
    if not link.startswith("vless://"):
        body = stable_subscription_body(user_id)
        if not body:
            raise web.HTTPNotFound(text="Subscription not found")
        return web.Response(
            text=body,
            content_type="text/plain; charset=utf-8",
            headers=happ_subscription_headers(user_id),
        )
    if CFG.subscription_format in ("json", "1", "true", "yes"):
        try:
            from happ_json_config import build_happ_json_subscription
            payload = build_happ_json_subscription(
                link,
                user_id=user_id,
                email=row_get(key, "email", ""),
                expires_at=row_get(key, "expires_at"),
            )
            return web.Response(
                text=json.dumps(payload, ensure_ascii=False),
                content_type="application/json",
                headers=happ_subscription_headers(user_id, key=key),
            )
        except Exception as e:
            logger.error("JSON subscription failed user=%s: %s", user_id, e)
    body = stable_subscription_body(user_id)
    if body:
        return web.Response(
            text=body,
            content_type="text/plain; charset=utf-8",
            headers=happ_subscription_headers(user_id),
        )
    raise web.HTTPNotFound(text="Subscription not found")


def sync_vpn_links_from_xui() -> None:
    """Сверка vless/subscription_url в bot.db с параметрами x-ui при старте."""
    try:
        inbound = xui._get_inbound()
        if not inbound:
            logger.warning("sync_vpn_links: x-ui inbound unavailable")
            return
        clients = xui._parse_clients(inbound)
        by_email = {c.get("email"): c for c in clients if c.get("email")}
        rows = db.fetchall(
            "SELECT user_id, email, vless_link, subscription_url FROM keys WHERE is_active = 1"
        )
        updated = 0
        for row in rows:
            client = by_email.get(row["email"])
            if not client:
                continue
            uid = int(row["user_id"])
            new_link = make_vless_link(client["id"], row["email"])
            sub_url = user_facing_subscription_link(uid)
            old_link = (row["vless_link"] or "").strip()
            old_sub = (row_get(row, "subscription_url", "") or "").strip()
            if new_link != old_link or sub_url != old_sub:
                db.execute(
                    "UPDATE keys SET vless_link = ?, subscription_url = ? WHERE user_id = ? AND is_active = 1",
                    (new_link, sub_url, uid),
                )
                updated += 1
        logger.info("sync_vpn_links: checked=%s updated=%s", len(rows), updated)
    except Exception:
        logger.exception("sync_vpn_links failed")


# =============================================================================
# HTTP SERVER + MAIN
# =============================================================================

async def start_http_server() -> None:
    app = web.Application()
    try:
        setup_web_auth_routes(app, db_path=CFG.db_path)
    except TypeError:
        # Старая копия web_auth_aiohttp без db_path — берёт DB_PATH только из окружения процесса.
        logger.warning(
            "setup_web_auth_routes без db_path — обновите web_auth_aiohttp.py рядом с bot_api.py "
            "(иначе БД веб-логина может расходиться с CFG.db_path)."
        )
        setup_web_auth_routes(app)
    app.router.add_post("/api/web/link-telegram",               api_web_link_telegram)
    app.router.add_post("/api/web/link-telegram/",              api_web_link_telegram)
    app.router.add_get( "/api/web/subscription-state",         api_web_subscription_state)
    app.router.add_get( "/api/web/subscription-state/",        api_web_subscription_state)
    app.router.add_post("/api/web/subscription/purchase",      api_web_subscription_purchase)
    app.router.add_post("/api/web/subscription/purchase/",     api_web_subscription_purchase)
    app.router.add_get( "/api/web/check-payment",              api_web_check_payment)
    app.router.add_get( "/api/web/check-payment/",             api_web_check_payment)
    app.router.add_post("/api/web/account-bootstrap",          api_web_account_bootstrap)
    app.router.add_post("/api/web/account-bootstrap/",         api_web_account_bootstrap)
    app.router.add_get( "/api/web/referrals-state",           api_web_referrals_state)
    app.router.add_get( "/api/web/referrals-state/",          api_web_referrals_state)
    app.router.add_get( "/api/web/promo/check",               api_web_promo_check)
    app.router.add_get( "/api/web/promo/check/",              api_web_promo_check)
    app.router.add_post("/crypto-webhook",                  handle_crypto_webhook)
    app.router.add_post("/platega-webhook",                 handle_platega_webhook)
    app.router.add_post("/api/platega-webhook",             handle_platega_webhook)
    app.router.add_post("/api/crypto-webhook",              handle_crypto_webhook)
    app.router.add_post("/api/issue-key",                   api_issue_key)
    app.router.add_post("/api/auth/telegram",               api_auth_telegram)
    app.router.add_post("/api/trial",                       api_trial)
    app.router.add_get( "/api/me",                          api_me)
    app.router.add_get( "/api/profile",                     api_me)
    app.router.add_get( "/api/user/me",                     api_me)
    app.router.add_get( "/api/account/me",                  api_me)
    app.router.add_get( "/api/history",                     api_history)
    app.router.add_get( "/api/payments",                    api_history)
    app.router.add_get( "/api/payments/history",            api_history)
    app.router.add_get( "/api/history/payments",            api_history)
    app.router.add_get( "/api/plans",                       api_plans)
    app.router.add_get( "/api/tariffs",                     api_plans)
    app.router.add_get( "/api/subscriptions/plans",         api_plans)
    app.router.add_get( "/api/devices",                     api_devices)
    app.router.add_get( "/api/user/devices",                api_devices)
    app.router.add_get( "/api/connections",                 api_devices)
    app.router.add_get( "/api/my-keys",                     api_my_keys)
    app.router.add_get( "/api/keys",                        api_my_keys)
    app.router.add_get( "/api/user/keys",                   api_my_keys)
    app.router.add_post("/api/subscription/purchase",       api_subscription_purchase)
    app.router.add_get( "/api/check-payment",               api_check_payment)
    app.router.add_post("/api/subscription/auto-renew",     api_subscription_auto_renew)
    app.router.add_post("/api/subscription/autorenew",      api_subscription_auto_renew)
    app.router.add_post("/api/autorenew",                   api_subscription_auto_renew)
    app.router.add_get( "/api/subscription/link",           api_subscription_link)
    app.router.add_get( "/miniapp/sub/{user_id}",          api_subscription_proxy)
    app.router.add_get( "/miniapp/sub/{user_id}/",         api_subscription_proxy)
    app.router.add_get( "/sub/{user_id}",                  api_subscription_proxy)
    app.router.add_get( "/sub/{user_id}/",                 api_subscription_proxy)
    app.router.add_get( "/api/referrals",                   api_referrals)
    app.router.add_get( "/api/wheel",                       api_wheel_state)
    app.router.add_get( "/api/wheel/",                      api_wheel_state)
    app.router.add_post("/api/wheel/spin",                  api_wheel_spin)
    app.router.add_post("/api/wheel/spin/",                 api_wheel_spin)
    app.router.add_post("/api/wheel/spin/paid",             api_wheel_spin_paid)
    app.router.add_post("/api/wheel/spin/paid/",            api_wheel_spin_paid)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", CFG.webhook_port)
    await site.start()
    logger.info("HTTP server started on port %s", CFG.webhook_port)


async def main() -> None:
    db.init()
    sync_vpn_links_from_xui()
    await bot.delete_webhook()
    logger.info("Telegram webhook removed; using polling")
    await start_http_server()
    asyncio.create_task(auto_check_payments())
    asyncio.create_task(auto_disable_expired_keys())
    asyncio.create_task(auto_renew_subscriptions())
    logger.info("Bot started")
    await dp.start_polling(bot)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Bot stopped")
