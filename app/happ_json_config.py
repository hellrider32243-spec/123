#!/usr/bin/env python3
"""
JSON-подписка для Happ в стиле UltimaVPN:
- активная: 7 профилей (Auto, Hysteria LTE, Турбо, Быстрый, Антиблок, LTE XHTTP, YouTube)
- истекшая: инфо-узлы «продлите через бот»
"""
from __future__ import annotations

import os
import sqlite3
import urllib.parse
from datetime import datetime, timezone
from typing import Any, Optional


def _env(name: str, default: str = "") -> str:
    return (os.getenv(name, default) or default).strip()


SUBSCRIPTION_FORMAT = _env("SUBSCRIPTION_FORMAT", "json").lower()
PUBLIC_HOST = _env("GRPC_PUBLIC_HOST", _env("PUBLIC_VLESS_HOST", "wingsvpn.shop"))
GRPC_PORT = int(_env("GRPC_INBOUND_PORT", _env("PUBLIC_VLESS_PORT", "8443")))
GRPC_SERVICE = _env("GRPC_SERVICE_NAME", "log")
REALITY_FP = _env("REALITY_FP", _env("GRPC_REALITY_FP", "safari"))
TCP_REALITY_FP = _env("TCP_REALITY_FP", _env("REALITY_FP", "chrome"))
JSON_FRAG_LENGTH = _env("JSON_FRAGMENT_LENGTH", "80-250")
JSON_FRAG_INTERVAL = _env("JSON_FRAGMENT_INTERVAL", "10-100")
JSON_FRAG_PACKETS = _env("JSON_FRAGMENT_PACKETS", "tlshello")
HAPP_FRAGMENT = _env("HAPP_FRAGMENT", "50-100,10-20,1-3")
GRPC_CLIENT_MULTIMODE = _env("GRPC_CLIENT_MULTIMODE", "true").lower() in ("1", "true", "yes")
REALITY_SNI = _env("SNI", _env("REALITY_SNI", "www.apple.com"))
REALITY_PBK = _env("REALITY_PBK", "")
REALITY_SID = _env("REALITY_SID", "d1dd")
PROFILE_AUTO = _env("VPN_PROFILE_AUTO", "🤖 Auto — умный выбор")
AUTO_BALANCER_TAG = _env("AUTO_BALANCER_TAG", "AUTO_BALANCER")
AUTO_OBS_INTERVAL = _env("AUTO_OBS_INTERVAL", _env("YOUTUBE_OBS_INTERVAL", "1h"))
AUTO_OBS_SAMPLING = int(_env("AUTO_OBS_SAMPLING", _env("YOUTUBE_OBS_SAMPLING", "2")) or "2")
PROFILE_HYSTERIA_LTE = _env("VPN_PROFILE_HYSTERIA_LTE", "🇪🇺 📡 Hysteria LTE")
HYSTERIA_PUBLIC_HOST = _env("HYSTERIA_PUBLIC_HOST", PUBLIC_HOST)
HYSTERIA_PORT = int(_env("HYSTERIA_PORT", "8447"))
HYSTERIA_SNI = _env("HYSTERIA_SNI", PUBLIC_HOST)
HYSTERIA_ALPN = [p for p in _env("HYSTERIA_ALPN", "h3").split(",") if p.strip()]
HYSTERIA_UP = _env("HYSTERIA_UP", "0")
HYSTERIA_DOWN = _env("HYSTERIA_DOWN", "0")
PROFILE_TURBO = _env("VPN_PROFILE_TURBO", "🇳🇱 Нидерланды — 🚀 Турбо")
PROFILE_FAST = _env("VPN_PROFILE_FAST", "⚡ Быстрый")
PROFILE_ANTIBLOCK = _env("VPN_PROFILE_ANTIBLOCK", "🛡 Антиблок")
PROFILE_XHTTP_LTE = _env(
    "VPN_PROFILE_XHTTP_LTE",
    "🇫🇮 🚀 Обход всего - работает даже на парковке!",
)
PROFILE_YOUTUBE = _env("VPN_PROFILE_YOUTUBE", "🇷🇺 Russia + Youtube без рекламы")
YOUTUBE_BALANCER_TAG = _env("YOUTUBE_BALANCER_TAG", "ALL_BALANCER")
YOUTUBE_OBS_INTERVAL = _env("YOUTUBE_OBS_INTERVAL", "1h")
YOUTUBE_OBS_SAMPLING = int(_env("YOUTUBE_OBS_SAMPLING", "2") or "2")
GRPC_TURBO_FP = _env("GRPC_TURBO_FP", _env("GRPC_REALITY_FP", "chrome"))
XHTTP_PUBLIC_HOST = _env("XHTTP_PUBLIC_HOST", PUBLIC_HOST)
XHTTP_PORT = int(_env("XHTTP_PORT", "8445"))
XHTTP_PATH = _env("XHTTP_PATH", "/api/v4/service")
XHTTP_FINGERPRINT = _env("XHTTP_FINGERPRINT", "firefox")
PROFILE_WHITELIST = _env("VPN_PROFILE_WHITELIST", "🇷🇺 LTE Белые Списки")
# Публичный порт TCP Reality (nginx stream :443 → xray 127.0.0.1:10443).
# TCP_INBOUND_PORT в .env — внутренний/legacy; клиентам всегда нужен 443.
TCP_CLIENT_PORT = int(_env("TCP_CLIENT_PORT", _env("TCP_PUBLIC_PORT", "443")))
TCP_PORT = TCP_CLIENT_PORT
WHITELIST_SNI = _env("WHITELIST_SNI", "hh.ru")
TCP_VLESS_FLOW = _env("TCP_VLESS_FLOW", "xtls-rprx-vision")
# Cloudflare-фронтинг: VLESS+WS+TLS через proxied-домен (обход блокировки IP сервера в РФ)
CF_WS_HOST = _env("CF_WS_HOST", "cf.wingsvpn.shop")
CF_WS_PORT = int(_env("CF_WS_PORT", "443"))
CF_WS_PATH = _env("CF_WS_PATH", "/cfws")
CF_WS_SNI = _env("CF_WS_SNI", CF_WS_HOST)
CF_WS_FP = _env("CF_WS_FP", "chrome")
PROFILE_CF = _env("VPN_PROFILE_CF", "☁️ Cloudflare — обход блокировок")
PROFILE_TITLE = _env("VPN_PROFILE_NAME", "TritonVPN")
COUNTRY_LABEL = _env("VPN_COUNTRY_LABEL", "🇩🇪 Германия")
VPN_MAX_DEVICES = max(1, int(_env("VPN_MAX_DEVICES", "2") or "2"))
BOT_USERNAME = _env("BOT_USERNAME", _env("BOT_LINK", "nordwingsvpn_bot").split("/")[-1] or "nordwingsvpn_bot")
BOT_TELEGRAM_URL = _env("BOT_TELEGRAM_URL", f"https://t.me/{BOT_USERNAME}")
XUI_DB_PATH = _env("XUI_DB_PATH", "/etc/x-ui/x-ui.db")
PROFILE_UPDATE_INTERVAL = _env("PROFILE_UPDATE_INTERVAL", "1")


def _telegram_direct_domains() -> list[str]:
    """Telegram в РФ работает напрямую; через VPS/DC часто отваливается."""
    return [
        "domain:telegram.org",
        "domain:telegram.me",
        "domain:t.me",
        "domain:tx.me",
        "domain:tdesktop.com",
        "domain:telegra.ph",
        "domain:telegram.dog",
        "domain:telesco.pe",
        "domain:telegram-cdn.org",
        "domain:cdn-telegram.org",
        "domain:telegram.space",
        "domain:legra.ph",
        "domain:graph.org",
        "domain:contest.com",
        "domain:fragment.com",
        "domain:tg.dev",
        "domain:comments.app",
        "domain:stel.com",
        "domain:nicegram.app",
    ]


def _telegram_direct_ips() -> list[str]:
    """Официальные DC/IP-диапазоны Telegram → direct (только IPv4: DNS UseIPv4)."""
    return [
        "91.108.4.0/22",
        "91.108.8.0/22",
        "91.108.12.0/22",
        "91.108.16.0/22",
        "91.108.20.0/22",
        "91.108.56.0/22",
        "149.154.160.0/20",
        "185.76.151.0/24",
    ]


def _telegram_direct_rules() -> list[dict[str, Any]]:
    return [
        {
            "domain": _telegram_direct_domains(),
            "outboundTag": "direct",
            "type": "field",
        },
        {
            "ip": _telegram_direct_ips(),
            "outboundTag": "direct",
            "type": "field",
        },
    ]




def parse_vless_link(link: str) -> dict[str, str]:
    out: dict[str, str] = {}
    if not link or not link.startswith("vless://"):
        return out
    body = link[8:]
    if "#" in body:
        main, remark = body.rsplit("#", 1)
        out["remark"] = urllib.parse.unquote(remark)
    else:
        main = body
    if "?" in main:
        hostpart, qs = main.split("?", 1)
        out["uuid"] = hostpart.split("@", 1)[0]
        for part in qs.split("&"):
            if "=" in part:
                k, v = part.split("=", 1)
                out[k] = urllib.parse.unquote(v)
    else:
        out["uuid"] = main.split("@", 1)[0]
    return out


def _clean_remark(raw: str) -> str:
    text = (raw or "").strip()
    if not text:
        return COUNTRY_LABEL
    if "_" in text:
        text = text.split("_", 1)[0].strip()
    for sep in (" — ", " - ", " | "):
        if sep in text:
            text = text.split(sep, 1)[0].strip()
    return text or COUNTRY_LABEL


def _display_name(profile: str, *, country: Optional[str] = None) -> str:
    country = (country or COUNTRY_LABEL).strip()
    profile = profile.strip()
    if country and country not in profile:
        return f"{country} — {profile}"
    return profile


def parse_expiry_ts(raw: str | None) -> Optional[int]:
    if not raw:
        return None
    text = str(raw).strip()
    if text.isdigit():
        val = int(text)
        return val // 1000 if val > 10_000_000_000 else val
    try:
        dt = datetime.fromisoformat(text.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return int(dt.timestamp())
    except Exception:
        return None


def is_expired(expires_at: str | None) -> bool:
    ts = parse_expiry_ts(expires_at)
    if not ts:
        return False
    return ts <= int(datetime.now(timezone.utc).timestamp())


def get_traffic_bytes(email: str) -> tuple[int, int]:
    email = (email or "").strip()
    if not email:
        return 0, 0
    try:
        conn = sqlite3.connect(XUI_DB_PATH)
        row = conn.execute(
            "SELECT up, down FROM client_traffics WHERE email = ? ORDER BY id DESC LIMIT 1",
            (email,),
        ).fetchone()
        conn.close()
        if row:
            return int(row[0] or 0), int(row[1] or 0)
    except Exception:
        pass
    return 0, 0



def _ultima_routing_rules() -> dict[str, Any]:
    """Точная схема UltimaVPN: .ru direct, остальное (default outbound) через VPN."""
    return {
        "domainMatcher": "hybrid",
        "domainStrategy": "IPIfNonMatch",
        "rules": [
            {"type": "field", "domain": ["oneme.ru", "max.ru"], "outboundTag": "block"},
            {"type": "field", "protocol": ["bittorrent"], "outboundTag": "direct"},
            {
                "type": "field",
                "domain": [
                    "avito.st",
                    "domain:yandex.com",
                    "domain:yandex.net",
                    "regexp:.*\\.ru$",
                    "regexp:.*\\.xn--p1ai$",
                    "regexp:.*\\.xn--p1acf$",
                    "regexp:.*\\.xn--p1ag$",
                ],
                "outboundTag": "direct",
            },
        ],
    }

def _routing_rules() -> dict[str, Any]:
    """Совместимость: базовый роутинг = UltimaVPN."""
    return _ultima_routing_rules()

def _whitelist_routing_rules() -> dict[str, Any]:
    """Ultima-роутинг + private direct."""
    rules = dict(_ultima_routing_rules())
    rules["rules"] = list(rules["rules"]) + [
        {"type": "field", "ip": ["geoip:private"], "outboundTag": "direct"},
    ]
    return rules

def _vk_proxy_domains() -> list[str]:
    """Экосистема VK → proxy: direct-доступ к VK не работает на ряде LTE-сетей."""
    return [
        "domain:vk.com",
        "domain:vk.ru",
        "domain:vkvideo.ru",
        "domain:vk.me",
        "domain:vk.cc",
        "domain:vk.link",
        "domain:userapi.com",
        "domain:vk-cdn.net",
        "domain:vk-cdn.me",
        "domain:vkcdnservice.com",
        "domain:mycdn.me",
        "domain:vkuservideo.net",
        "domain:vkuseraudio.net",
        "domain:vkapps.com",
        "domain:vk-portal.net",
        "domain:vkpay.io",
        "domain:mvk.com",
        "domain:ok.ru",
        "domain:okcdn.ru",
        "domain:mail.ru",
        "domain:imgsmail.ru",
        "domain:mradx.net",
    ]


def _vk_proxy_ips() -> list[str]:
    """IP-диапазоны VK (AS47541/AS47542) → proxy, до правила geoip:ru → direct."""
    return [
        "87.240.128.0/18",
        "93.186.224.0/20",
        "95.142.192.0/20",
        "95.213.0.0/17",
        "155.133.0.0/16",
        "185.32.248.0/22",
    ]


def _xhttp_lte_routing_rules() -> dict[str, Any]:
    """Split-tunnel как RaivoVPN: RU direct, VK/TikTok proxy, остальное proxy."""
    return {
        "domainMatcher": "hybrid",
        "domainStrategy": "IPIfNonMatch",
        "rules": [
            {
                "domain": ["domain:sputnik.systems", "domain:storage.yandexcloud.net"],
                "outboundTag": "direct",
                "type": "field",
            },
            *_telegram_direct_rules(),
            # VK ломается при direct на LTE (DPI) — до всех RU-direct правил
            {
                "domain": _vk_proxy_domains(),
                "outboundTag": "proxy",
                "type": "field",
            },
            {
                "ip": _vk_proxy_ips(),
                "outboundTag": "proxy",
                "type": "field",
            },
            {
                "domain": [
                    "domain:tiktok.com",
                    "domain:tiktokv.com",
                    "domain:tiktokcdn.com",
                    "domain:byteoversea.com",
                    "domain:musical.ly",
                ],
                "outboundTag": "proxy",
                "type": "field",
            },
            {
                "domain": [
                    "domain:appmetrica.yandex.net",
                    "domain:mobile.yandex.net",
                    "domain:app-measurement.com",
                    "domain:crashlytics.com",
                    "domain:sentry.io",
                    "domain:adjust.com",
                    "domain:appsflyer.com",
                    "domain:appsflyersdk.com",
                    "domain:branch.io",
                    "domain:app.link",
                ],
                "outboundTag": "direct",
                "type": "field",
            },
            {
                "domain": [
                    "domain:wildberries.ru",
                    "domain:wb.ru",
                    "domain:ozon.ru",
                    "domain:avito.ru",
                    "domain:gosuslugi.ru",
                    "domain:samokat.ru",
                ],
                "outboundTag": "direct",
                "type": "field",
            },
            {
                "domain": [
                    "full:checkip.amazonaws.com",
                    "domain:2ip.ru",
                    "domain:2ip.io",
                    "domain:ifconfig.me",
                    "domain:ipify.org",
                    "domain:ipinfo.io",
                    "domain:whoer.net",
                    "domain:icanhazip.com",
                ],
                "outboundTag": "direct",
                "type": "field",
            },
            {
                "domain": [
                    "regexp:^([A-Za-z0-9-]+\\.)+ru$",
                    "regexp:^([A-Za-z0-9-]+\\.)+su$",
                    "regexp:^([A-Za-z0-9-]+\\.)+xn--p1ai$",
                ],
                "outboundTag": "direct",
                "type": "field",
            },
            {
                "domain": [
                    "domain:youtube.com",
                    "domain:youtu.be",
                    "domain:ytimg.com",
                    "domain:googlevideo.com",
                    "domain:ggpht.com",
                    "domain:googleapis.com",
                    "domain:gstatic.com",
                    "domain:youtubei.googleapis.com",
                    "domain:google.com",
                    "domain:gvt1.com",
                ],
                "outboundTag": "proxy",
                "type": "field",
            },
            {"ip": ["geoip:ru"], "outboundTag": "direct", "type": "field"},
            {
                "domain": [
                    "domain:hh.ru",
                    "domain:yandex.ru",
                    "domain:ya.ru",
                    "domain:megafon.ru",
                    "domain:beeline.ru",
                    "domain:t2.ru",
                    "domain:vtb.ru",
                    "domain:sberbank.ru",
                    "domain:rutube.ru",
                    "domain:dzen.ru",
                ],
                "outboundTag": "direct",
                "type": "field",
            },
            {"outboundTag": "direct", "protocol": ["bittorrent"], "type": "field"},
            {"network": "tcp,udp", "outboundTag": "proxy", "type": "field"},
        ],
    }


def _core_ad_block_domains() -> list[str]:
    """Geosite + явные рекламные/трекинговые домены → block.

    НЕ блокируем googlevideo.com, youtubei.googleapis.com, ytimg.com —
    иначе ломается воспроизведение YouTube.
    appmetrica.yandex.net не блокируем — ломает аналитику приложений.
    """
    return [
        # Google / YouTube ads
        "domain:doubleclick.net",
        "domain:googlesyndication.com",
        "domain:googleadservices.com",
        "domain:googletagservices.com",
        "domain:googletagmanager.com",
        "domain:adservice.google.com",
        "domain:ads.google.com",
        "domain:ads.youtube.com",
        "domain:pagead2.googlesyndication.com",
        "domain:static.doubleclick.net",
        "domain:ad.doubleclick.net",
        "domain:googleads.g.doubleclick.net",
        "domain:pubads.g.doubleclick.net",
        "domain:securepubads.g.doubleclick.net",
        "domain:tpc.googlesyndication.com",
        "domain:imasdk.googleapis.com",
        "domain:pagead-googlehosted.l.google.com",
        "domain:partner.googleadservices.com",
        "domain:adservice.google.ru",
        "domain:adservice.google.com.ua",
        "domain:google-analytics.com",
        "domain:analytics.google.com",
        "domain:ssl.google-analytics.com",
        "domain:stats.g.doubleclick.net",
        "domain:fls.doubleclick.net",
        "domain:2mdn.net",
        # Meta / Facebook ads (не facebook.com — ломает приложение)
        "domain:connect.facebook.net",
        "domain:pixel.facebook.com",
        "domain:an.facebook.com",
        "domain:ads.facebook.com",
        # Yandex ads / metrika (не appmetrica — см. docstring)
        "domain:adfox.ru",
        "domain:adriver.ru",
        "domain:an.yandex.ru",
        "domain:mc.yandex.ru",
        "domain:metrika.yandex.ru",
        "domain:ads.yandex.ru",
        "domain:analytic.yandex.ru",
        "domain:awaps.yandex.ru",
        "domain:bs.yandex.ru",
        "domain:clck.yandex.ru",
        "domain:extmaps.yandex.ru",
        "domain:informer.yandex.ru",
        "domain:strm.yandex.ru",
        "domain:yabs.yandex.ru",
        "domain:yandexadexchange.net",
        "domain:direct.yandex.ru",
        # RU ad / tracking
        "domain:advmaker.net",
        "domain:advmaker.ru",
        "domain:adtarget.me",
        "domain:adtarget.ru",
        "domain:top100.rambler.ru",
        "domain:counter.rambler.ru",
        "domain:webvisor.org",
        "domain:hotlog.ru",
        "domain:top.mail.ru",
        "domain:tns-counter.ru",
        "domain:mediametrics.ru",
        "domain:adplay.ru",
        "domain:flocktory.com",
        "domain:sb.scorecardresearch.com",
        # Global ad networks
        "domain:taboola.com",
        "domain:trc.taboola.com",
        "domain:cdn.taboola.com",
        "domain:outbrain.com",
        "domain:widgets.outbrain.com",
        "domain:criteo.com",
        "domain:static.criteo.net",
        "domain:adsrvr.org",
        "domain:openx.net",
        "domain:rubiconproject.com",
        "domain:pubmatic.com",
        "domain:adnxs.com",
        "domain:adsymptotic.com",
        "domain:advertising.com",
        "domain:adform.net",
        "domain:adform.com",
        "domain:smartadserver.com",
        "domain:contextweb.com",
        "domain:lijit.com",
        "domain:quantserve.com",
        "domain:scorecardresearch.com",
        "domain:moatads.com",
        "domain:adsafeprotected.com",
        "domain:doubleverify.com",
        "domain:imrworldwide.com",
        "domain:exelator.com",
        "domain:bluekai.com",
        "domain:krxd.net",
        "domain:rlcdn.com",
        "domain:tapad.com",
        "domain:turn.com",
        "domain:mathtag.com",
        "domain:everesttech.net",
        "domain:demdex.net",
        "domain:omtrdc.net",
        "domain:admob.com",
        "domain:applovin.com",
        "domain:unityads.unity3d.com",
        "domain:ironsrc.com",
        "domain:supersonicads.com",
        "domain:vungle.com",
        "domain:chartboost.com",
        "domain:tapjoy.com",
        "domain:mopub.com",
        "domain:inmobi.com",
        "domain:adcolony.com",
        "domain:fyber.com",
        "domain:inner-active.mobi",
        "domain:startapp.com",
        "domain:admarvel.com",
        "domain:adswizz.com",
        "domain:spotxchange.com",
        "domain:spotx.tv",
        "domain:teads.tv",
        "domain:teads.com",
        "domain:mgid.com",
        "domain:revcontent.com",
        "domain:zemanta.com",
        "domain:bidr.io",
        "domain:bidswitch.net",
        "domain:casalemedia.com",
        "domain:33across.com",
        "domain:sharethrough.com",
        "domain:triplelift.com",
        "domain:indexexchange.com",
        "domain:mediamath.com",
        "domain:thetradedesk.com",
        "domain:amazon-adsystem.com",
        "domain:aax.amazon-adsystem.com",
        "domain:adtech.de",
        "domain:adtechus.com",
        "domain:adition.com",
        "domain:yieldlab.net",
        "domain:yieldmo.com",
        "domain:sovrn.com",
        "domain:sonobi.com",
        "domain:undertone.com",
        "domain:exponential.com",
        "domain:tidaltv.com",
        "domain:eyeota.net",
        "domain:lotame.com",
        "domain:neustar.biz",
        "domain:agkn.com",
        "domain:adgrx.com",
        "domain:adentifi.com",
        "domain:adroll.com",
        "domain:simpli.fi",
        "domain:admanmedia.com",
        "domain:admixer.net",
        "domain:adscale.de",
        "domain:adsup.com",
        "domain:adtech.com",
        "domain:adtilt.com",
        "domain:adtrue.com",
        "domain:adverline.com",
        "domain:adverty.com",
        "domain:adview.com",
        "domain:adzerk.net",
        "domain:adzmedia.com",
        "domain:adzuna.com",
        "domain:adzymic.com",
        # Mobile attribution (ads-focused)
        "domain:appsflyer.com",
        "domain:appsflyersdk.com",
        "domain:adjust.com",
        "domain:branch.io",
        "domain:app.link",
        "domain:kochava.com",
        "domain:tenjin.io",
        "domain:singular.net",
        "domain:app-measurement.com",
        # Microsoft / Amazon ads
        "domain:ads.microsoft.com",
        "domain:bingads.microsoft.com",
        "domain:a-ads.amazon-adsystem.com",
        "domain:assoc-amazon.com",
        # TikTok ads
        "domain:ads.tiktok.com",
        "domain:analytics.tiktok.com",
        # Twitter/X ads
        "domain:ads-twitter.com",
        "domain:analytics.twitter.com",
        "domain:ads-api.twitter.com",
    ]


def _youtube_ad_block_domains() -> list[str]:
    """Обратная совместимость — делегирует в _core_ad_block_domains."""
    return _core_ad_block_domains()


def _youtube_ad_dns_hosts() -> dict[str, str]:
    """DNS null-route для чистых рекламных доменов (дополнение к routing block)."""
    return _ad_block_dns_hosts()


def _ad_block_dns_hosts() -> dict[str, str]:
    """DNS null-route для явных рекламных доменов (geosite обрабатывает routing)."""
    hosts: dict[str, str] = {}
    for entry in _core_ad_block_domains():
        if entry.startswith("geosite:"):
            continue
        bare = entry.split(":", 1)[-1] if ":" in entry else entry
        hosts[bare] = "0.0.0.0"
    return hosts


def _youtube_balancer_dns() -> dict[str, Any]:
    # Без DNS hosts→0.0.0.0: на Happ/LTE это ломает резолв рядом с Google/Telegram.
    # Реклама режется routing → block.
    return {
        "queryStrategy": "UseIP",
        "servers": ["1.1.1.1", "1.0.0.1"],
    }


def _youtube_ru_direct_domains() -> list[str]:
    """RU/SU домены и сервисы → direct (список как у tconnect)."""
    return [
        "regexp:(^|\\.)ru$",
        "regexp:(^|\\.)su$",
        "regexp:(^|\\.)xn--p1ai$",
        "domain:vk.com",
        "domain:userapi.com",
        "domain:vk-cdn.net",
        "domain:mycdn.me",
        "domain:vkcdnservice.com",
        "domain:vk.me",
        "domain:vk.cc",
        "domain:vkpay.io",
        "domain:vkuservideo.net",
        "domain:vkuseraudio.net",
        "domain:vkapps.com",
        "domain:vk-portal.net",
        "regexp:(^|\\.)yandex\\.net$",
        "regexp:(^|\\.)2gis\\.(ae|am|az|by|com|com\\.cy|cz|ge|kg|kz|tj|ua|uz)$",
        "domain:avito.st",
        "regexp:(^|\\.)ozon\\.(by|com|kz|tm)$",
        "regexp:(^|\\.)ozon\\.com\\.(by|kz)$",
        "domain:ozonru.me",
        "domain:ozonusercontent.com",
        "domain:paywb.com",
        "regexp:^alfa(-?[a-z]+)?\\.(com|biz|st)$",
        "regexp:^vtb(-?[a-z0-9]+)?\\.(com|in|digital|site|bank\\.in|promo)$",
        "domain:1cfresh.com",
        "domain:1internet.tv",
        "domain:4meeting.me",
        "domain:5post.market",
        "domain:8ofpsm7zqu.a.trbcdn.net",
        "domain:alformacap.com",
        "domain:alformacapital.com",
        "domain:apeople.site",
        "domain:banka-ui.dev",
        "domain:beta-bank.com",
        "domain:boosty.to",
        "domain:bronevik.com",
        "domain:chizhik.club",
        "domain:clstorage.net",
        "domain:d5de4k0ri8jba7ucdbt6.apigw.yandexcloud.net",
        "domain:dbo-dengi.online",
        "domain:flocktory.com",
        "domain:sb.scorecardresearch.com",
        "domain:xn--90aifd0aza.site",
        "domain:mtalk.google.com",
        "domain:push.apple.com",
        "domain:push-apple.com.akadns.net",
    ]


def _youtube_ru_direct_ips() -> list[str]:
    """RU IP-диапазоны → direct (tconnect + geoip:ru)."""
    return [
        "geoip:ru",
        "5.61.16.0/21",
        "46.226.122.0/24",
        "85.198.76.0/22",
        "87.240.128.0/18",
        "91.212.64.0/24",
        "91.223.63.0/24",
        "91.223.93.0/24",
        "91.230.107.0/24",
        "93.186.224.0/21",
        "95.213.0.0/17",
        "176.114.120.0/21",
        "185.16.148.0/22",
        "185.16.244.0/22",
        "185.32.248.0/22",
        "185.62.200.0/23",
        "185.62.202.0/24",
        "185.73.192.0/22",
        "185.89.12.0/24",
        "185.89.14.0/23",
        "185.138.252.0/22",
        "185.179.144.0/22",
        "193.200.10.0/23",
        "194.1.214.0/24",
        "195.34.20.0/23",
        "195.242.82.0/23",
        "213.184.155.0/24",
        "213.184.156.0/22",
        "217.12.96.0/21",
        "217.12.104.0/23",
        "217.12.106.0/24",
        "217.12.110.0/24",
        "217.14.48.0/20",
        "217.20.144.0/20",
    ]


def _youtube_proxy_outbound_tags() -> list[str]:
    return ["pr_YT_TCP", "pr_YT_GRPC", "pr_YT_XHTTP"]


def _youtube_burst_observatory() -> dict[str, Any]:
    return {
        "subjectSelector": _youtube_proxy_outbound_tags(),
        "pingConfig": {
            "connectivity": "http://connectivitycheck.gstatic.com/generate_204",
            "destination": "http://www.gstatic.com/generate_204",
            "interval": YOUTUBE_OBS_INTERVAL,
            "sampling": YOUTUBE_OBS_SAMPLING,
            "timeout": "5s",
        },
    }


def _youtube_balancer_routing_rules() -> dict[str, Any]:
    """Split-tunnel + leastLoad balancer (архитектура tconnect на wingsvpn.shop)."""
    return {
        "domainMatcher": "hybrid",
        "domainStrategy": "IPIfNonMatch",
        "balancers": [
            {
                "tag": YOUTUBE_BALANCER_TAG,
                "selector": _youtube_proxy_outbound_tags(),
                "strategy": {
                    "type": "leastLoad",
                    "settings": {
                        "baselines": ["500ms"],
                        "costs": [
                            {"match": "pr_YT_TCP", "value": 1},
                            {"match": "pr_YT_GRPC", "value": 50},
                            {"match": "pr_YT_XHTTP", "value": 80},
                        ],
                        "expected": 1,
                        "maxRTT": "1500ms",
                        "tolerance": 0.1,
                    },
                },
                "fallbackTag": "pr_YT_TCP",
            }
        ],
        "rules": [
            {
                "domain": _youtube_ad_block_domains(),
                "outboundTag": "block",
                "type": "field",
            },
            {"outboundTag": "direct", "protocol": ["bittorrent"], "type": "field"},
            *_telegram_direct_rules(),
            {"ip": ["geoip:private"], "outboundTag": "direct", "type": "field"},
            {"domain": ["oneme.ru", "max.ru"], "outboundTag": "direct", "type": "field"},
            # YouTube/Google ДО geoip:ru — иначе часть CDN уходит direct и режется LTE/DPI
            {
                "domain": [
                    "domain:youtube.com",
                    "domain:youtu.be",
                    "domain:yt.be",
                    "domain:ytimg.com",
                    "domain:googlevideo.com",
                    "domain:ggpht.com",
                    "domain:googleapis.com",
                    "domain:gstatic.com",
                    "domain:google.com",
                    "domain:google.ru",
                    "domain:youtubekids.com",
                    "domain:youtube-nocookie.com",
                    "domain:withyoutube.com",
                    "domain:gvt1.com",
                    "domain:wide-youtube.l.google.com",
                    "domain:youtubei.googleapis.com",
                    "domain:youtube.googleapis.com",
                    "domain:youtubeembeddedplayer.googleapis.com",
                    "domain:music.youtube.com",
                    "domain:yt3.ggpht.com",
                    "domain:jnn-pa.googleapis.com",
                ],
                "balancerTag": YOUTUBE_BALANCER_TAG,
                "type": "field",
            },
            {
                "domain": _youtube_ru_direct_domains(),
                "outboundTag": "direct",
                "type": "field",
            },
            {
                "ip": _youtube_ru_direct_ips(),
                "outboundTag": "direct",
                "type": "field",
            },
            {
                "balancerTag": YOUTUBE_BALANCER_TAG,
                "network": "tcp,udp",
                "type": "field",
            },
        ],
    }

def _auto_proxy_outbound_tags() -> list[str]:
    return ["pr_AUTO_TCP", "pr_AUTO_GRPC", "pr_AUTO_XHTTP"]


def _auto_burst_observatory() -> dict[str, Any]:
    return {
        "subjectSelector": _auto_proxy_outbound_tags(),
        "pingConfig": {
            "connectivity": "http://connectivitycheck.gstatic.com/generate_204",
            "destination": "http://www.gstatic.com/generate_204",
            "interval": AUTO_OBS_INTERVAL,
            "sampling": AUTO_OBS_SAMPLING,
            "timeout": "5s",
        },
    }


def _auto_balancer_routing_rules() -> dict[str, Any]:
    """Split-tunnel + leastLoad: RU/gov direct, TikTok через балансер, остальное — лучший outbound."""
    return {
        "domainMatcher": "hybrid",
        "domainStrategy": "IPIfNonMatch",
        "balancers": [
            {
                "tag": AUTO_BALANCER_TAG,
                "selector": _auto_proxy_outbound_tags(),
                "strategy": {
                    "type": "leastLoad",
                    "settings": {
                        "baselines": ["500ms"],
                        "costs": [
                            {"match": "pr_AUTO_TCP", "value": 1},
                            {"match": "pr_AUTO_GRPC", "value": 50},
                            {"match": "pr_AUTO_XHTTP", "value": 80},
                        ],
                        "expected": 1,
                        "maxRTT": "1500ms",
                        "tolerance": 0.1,
                    },
                },
                "fallbackTag": "pr_AUTO_TCP",
            }
        ],
        "rules": [
            {"outboundTag": "direct", "protocol": ["bittorrent"], "type": "field"},
            {"domain": ["oneme.ru", "max.ru"], "outboundTag": "direct", "type": "field"},
            *_telegram_direct_rules(),
            {"ip": ["geoip:private"], "outboundTag": "direct", "type": "field"},
            {
                "domain": [
                    "domain:appmetrica.yandex.net",
                    "domain:mobile.yandex.net",
                    "domain:app-measurement.com",
                    "domain:crashlytics.com",
                    "domain:sentry.io",
                    "domain:adjust.com",
                    "domain:appsflyer.com",
                    "domain:appsflyersdk.com",
                    "domain:branch.io",
                    "domain:app.link",
                ],
                "outboundTag": "direct",
                "type": "field",
            },
            {
                "domain": [
                    "domain:wildberries.ru",
                    "domain:wb.ru",
                    "domain:ozon.ru",
                    "domain:avito.ru",
                    "domain:gosuslugi.ru",
                    "domain:samokat.ru",
                ],
                "outboundTag": "direct",
                "type": "field",
            },
            {
                "domain": [
                    "full:checkip.amazonaws.com",
                    "domain:2ip.ru",
                    "domain:2ip.io",
                    "domain:ifconfig.me",
                    "domain:ipify.org",
                    "domain:ipinfo.io",
                    "domain:whoer.net",
                    "domain:icanhazip.com",
                ],
                "outboundTag": "direct",
                "type": "field",
            },
            {
                "domain": [
                    "regexp:^([A-Za-z0-9-]+\\.)+ru$",
                    "regexp:^([A-Za-z0-9-]+\\.)+su$",
                    "regexp:^([A-Za-z0-9-]+\\.)+xn--p1ai$",
                ],
                "outboundTag": "direct",
                "type": "field",
            },
            {
                "domain": [
                    "domain:youtube.com",
                    "domain:youtu.be",
                    "domain:ytimg.com",
                    "domain:googlevideo.com",
                    "domain:ggpht.com",
                    "domain:googleapis.com",
                    "domain:gstatic.com",
                    "domain:youtubei.googleapis.com",
                    "domain:gvt1.com",
                ],
                "balancerTag": AUTO_BALANCER_TAG,
                "type": "field",
            },
            {"ip": ["geoip:ru"], "outboundTag": "direct", "type": "field"},
            {
                "domain": [
                    "domain:hh.ru",
                    "domain:yandex.ru",
                    "domain:ya.ru",
                    "domain:vk.com",
                    "domain:mail.ru",
                    "domain:megafon.ru",
                    "domain:beeline.ru",
                    "domain:t2.ru",
                    "domain:vtb.ru",
                    "domain:sberbank.ru",
                    "domain:rutube.ru",
                    "domain:dzen.ru",
                ],
                "outboundTag": "direct",
                "type": "field",
            },
            {
                "domain": [
                    "domain:tiktok.com",
                    "domain:tiktokv.com",
                    "domain:tiktokcdn.com",
                    "domain:byteoversea.com",
                    "domain:musical.ly",
                ],
                "balancerTag": AUTO_BALANCER_TAG,
                "type": "field",
            },
            {
                "balancerTag": AUTO_BALANCER_TAG,
                "network": "tcp,udp",
                "type": "field",
            },
        ],
    }


def _turbo_routing_rules() -> dict[str, Any]:
    """Минимум правил — меньше накладных расходов на маршрутизацию."""
    return {
        "domainMatcher": "hybrid",
        "domainStrategy": "IPIfNonMatch",
        "rules": [
            {"domain": ["oneme.ru", "max.ru"], "outboundTag": "block", "type": "field"},
            {"outboundTag": "direct", "protocol": ["bittorrent"], "type": "field"},
            *_telegram_direct_rules(),
        ],
    }


def _client_inbounds(*, route_only: bool = False) -> list[dict[str, Any]]:
    sniffing = {
        "destOverride": ["http", "tls", "quic"],
        "enabled": True,
        "routeOnly": route_only,
    }
    return [
        {
            "listen": "127.0.0.1",
            "port": 10808,
            "protocol": "socks",
            "settings": {"auth": "noauth", "udp": True},
            "sniffing": sniffing,
            "tag": "socks",
        },
        {
            "listen": "127.0.0.1",
            "port": 10809,
            "protocol": "http",
            "settings": {"allowTransparent": False},
            "sniffing": sniffing,
            "tag": "http",
        },
    ]


def _happ_meta(
    *,
    user_id: Optional[int] = None,
    expired: bool = False,
    extra: Optional[dict[str, str]] = None,
) -> dict[str, str]:
    if expired:
        meta = {
            "sub-info-text": "Срок вашей подписки истёк.",
            "sub-info-color": "red",
            "serverDescription": "Продлите доступ в Telegram-боте",
        }
    else:
        hint = (
            f"{user_id} • 🤖 Auto · 📡 Hysteria · 🚀 Турбо · 🇫🇮 Обход"
            if user_id
            else "🤖 Auto · 📡 Hysteria · 🚀 Турбо · 🇫🇮 Обход"
        )
        meta = {
            "sub-info-text": hint[:200],
            "sub-info-color": "blue",
            "serverDescription": f"📱 До {VPN_MAX_DEVICES} устройств · безлимит",
        }
    if extra:
        meta.update(extra)
    return meta


def _base_config(
    remark: str,
    proxy_outbound: dict[str, Any],
    *,
    meta: Optional[dict[str, str]] = None,
    routing: Optional[dict[str, Any]] = None,
    dns: Optional[dict[str, Any]] = None,
    dns_servers: Optional[list[str]] = None,
    route_only: bool = False,
) -> dict[str, Any]:
    return {
        "dns": dns or {"queryStrategy": "UseIP", "servers": dns_servers or ["8.8.8.8", "8.8.4.4"]},
        "inbounds": _client_inbounds(route_only=route_only),
        "log": {"loglevel": "error"},
        "outbounds": [
            proxy_outbound,
            {"protocol": "freedom", "tag": "direct"},
            {"protocol": "blackhole", "tag": "block"},
        ],
        "remarks": remark,
        "meta": meta or _happ_meta(),
        "routing": routing or _routing_rules(),
    }


def _balancer_config(
    remark: str,
    proxy_outbounds: list[dict[str, Any]],
    *,
    meta: Optional[dict[str, str]] = None,
    routing: Optional[dict[str, Any]] = None,
    dns: Optional[dict[str, Any]] = None,
    burst_observatory: Optional[dict[str, Any]] = None,
    route_only: bool = False,
) -> dict[str, Any]:
    cfg: dict[str, Any] = {
        "dns": dns or {"queryStrategy": "UseIP", "servers": ["8.8.8.8", "8.8.4.4"]},
        "inbounds": _client_inbounds(route_only=route_only),
        "log": {"loglevel": "error"},
        "outbounds": [
            *proxy_outbounds,
            {"protocol": "freedom", "tag": "direct"},
            {"protocol": "blackhole", "tag": "block"},
        ],
        "remarks": remark,
        "meta": meta or _happ_meta(),
        "routing": routing or _routing_rules(),
    }
    if burst_observatory:
        cfg["burstObservatory"] = burst_observatory
    return cfg


def _happ_fragment_settings() -> dict[str, str]:
    # UltimaVPN: packets 1-3, length 50-100, interval 10-20
    parts = (HAPP_FRAGMENT or "50-100,10-20,1-3").split(",")
    return {
        "length": (parts[0] if len(parts) > 0 else JSON_FRAG_LENGTH) or "50-100",
        "interval": (parts[1] if len(parts) > 1 else JSON_FRAG_INTERVAL) or "10-20",
        "packets": (parts[2] if len(parts) > 2 else JSON_FRAG_PACKETS) or "1-3",
    }


def _apply_fragment(outbound: dict[str, Any]) -> None:
    frag = _happ_fragment_settings()
    outbound["fragment"] = {
        "length": frag["length"],
        "interval": frag["interval"],
        "packets": frag["packets"],
    }


def _grpc_outbound(
    client_uuid: str,
    *,
    host: str,
    port: int,
    sni: str,
    pbk: str,
    sid: str,
    service_name: str,
    fingerprint: str,
    with_fragment: bool = True,
    tag: str = "proxy",
) -> dict[str, Any]:
    outbound: dict[str, Any] = {
        "protocol": "vless",
        "settings": {
            "vnext": [
                {
                    "address": host,
                    "port": port,
                    "users": [{"encryption": "none", "flow": "", "id": client_uuid}],
                }
            ]
        },
        "streamSettings": {
            "grpcSettings": {
                "authority": "",
                "mode": False,
                "multiMode": GRPC_CLIENT_MULTIMODE,
                "serviceName": service_name,
            },
            "network": "grpc",
            "realitySettings": {
                "fingerprint": fingerprint,
                "publicKey": pbk,
                "serverName": sni,
                "shortId": sid,
                "show": False,
            },
            "security": "reality",
        },
        "tag": tag,
    }
    if with_fragment:
        _apply_fragment(outbound)
    return outbound


def _grpc_turbo_outbound(
    client_uuid: str,
    *,
    host: str,
    port: int,
    sni: str,
    pbk: str,
    sid: str,
    service_name: str,
    fingerprint: str,
) -> dict[str, Any]:
    """gRPC Reality с максимальными настройками скорости для Happ."""
    outbound = _grpc_outbound(
        client_uuid,
        host=host,
        port=port,
        sni=sni,
        pbk=pbk,
        sid=sid,
        service_name=service_name,
        fingerprint=fingerprint,
        with_fragment=True,
    )
    # Только клиентские gRPC-параметры — серверные (idle_timeout, sockopt и т.д.)
    # ломают подключение в Happ, их настраивает tune_grpc_speed.py на сервере.
    return outbound


def _xhttp_extra_settings() -> dict[str, Any]:
    """Клиентские параметры XHTTP (маскировка под REST API), как у RaivoVPN."""
    return {
        "headers": {
            "Accept": "application/vnd.api+json, application/json, text/plain, */*",
            "Accept-Language": "ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7",
            "Cache-Control": "no-cache",
            "Pragma": "no-cache",
        },
        "scMaxBufferedPosts": 32,
        "scMaxEachPostBytes": "1536-6144",
        "scMinPostsIntervalMs": "4-18",
        "seqKey": "offset",
        "seqPlacement": "query",
        "serverMaxHeaderBytes": 32768,
        "uplinkDataKey": "X-Playback-Token",
        "uplinkDataPlacement": "header",
        "uplinkHTTPMethod": "GET",
        "xmux": {
            "cMaxReuseTimes": "36-96",
            "hKeepAlivePeriod": 0,
            "hMaxRequestTimes": "320-640",
            "hMaxReusableSecs": "720-1800",
            "maxConcurrency": "6-16",
        },
        "xPaddingBytes": "48-320",
        "xPaddingHeader": "X-Rewrite-URL",
        "xPaddingKey": "q",
        "xPaddingMethod": "tokenish",
        "xPaddingObfsMode": True,
        "xPaddingPlacement": "queryInHeader",
    }


def _xhttp_outbound(
    client_uuid: str,
    *,
    host: str,
    port: int,
    path: str,
    fingerprint: str,
    tag: str = "proxy",
    with_fragment: bool = True,
) -> dict[str, Any]:
    outbound: dict[str, Any] = {
        "protocol": "vless",
        "settings": {
            "vnext": [
                {
                    "address": host,
                    "port": port,
                    "users": [{"encryption": "none", "flow": "", "id": client_uuid}],
                }
            ]
        },
        "streamSettings": {
            "network": "xhttp",
            "security": "tls",
            "tlsSettings": {
                "alpn": ["h2", "http/1.1"],
                "fingerprint": fingerprint,
                "serverName": host,
            },
            "xhttpSettings": {
                "extra": _xhttp_extra_settings(),
                "host": host,
                "mode": "packet-up",
                "path": path,
            },
        },
        "tag": tag,
    }
    # fragment на XHTTP в Happ/LTE иногда даёт «подключился — нет интернета»
    return outbound


def _ws_outbound(
    client_uuid: str,
    *,
    host: str,
    port: int,
    path: str,
    sni: str,
    fingerprint: str,
    tag: str = "proxy",
) -> dict[str, Any]:
    """VLESS + WebSocket + TLS. Через Cloudflare (proxied) клиент коннектится к IP CF,
    поэтому блокировка IP сервера в РФ не срабатывает. SNI = чистый домен cf.*."""
    return {
        "protocol": "vless",
        "settings": {
            "vnext": [
                {
                    "address": host,
                    "port": port,
                    "users": [{"encryption": "none", "flow": "", "id": client_uuid}],
                }
            ]
        },
        "streamSettings": {
            "network": "ws",
            "security": "tls",
            "tlsSettings": {
                "alpn": ["http/1.1"],
                "fingerprint": fingerprint,
                "serverName": sni,
            },
            "wsSettings": {
                "path": path,
                "headers": {"Host": host},
            },
        },
        "tag": tag,
    }


def _tcp_outbound(
    client_uuid: str,
    *,
    host: str,
    port: int,
    sni: str,
    pbk: str,
    sid: str,
    fingerprint: str,
    flow: str = "",
    with_fragment: bool = False,
    tag: str = "proxy",
) -> dict[str, Any]:
    outbound: dict[str, Any] = {
        "protocol": "vless",
        "settings": {
            "vnext": [
                {
                    "address": host,
                    "port": port,
                    "users": [{"encryption": "none", "flow": flow, "id": client_uuid}],
                }
            ]
        },
        "streamSettings": {
            "network": "tcp",
            "realitySettings": {
                "fingerprint": fingerprint,
                "publicKey": pbk,
                "serverName": sni,
                "shortId": sid,
                "show": False,
            },
            "security": "reality",
            "tcpSettings": {},
        },
        "tag": tag,
    }
    # Fragment на TCP Reality через nginx stream ломает SNI-preread → после connect интернет умирает.
    return outbound


def _hysteria2_outbound(
    client_uuid: str,
    *,
    host: str,
    port: int,
    sni: str,
    auth: Optional[str] = None,
    up: Optional[str] = None,
    down: Optional[str] = None,
    alpn: Optional[list[str]] = None,
    tag: str = "proxy",
) -> dict[str, Any]:
    """Xray hysteria outbound (v2) — совместим с официальным Hysteria2 server."""
    hysteria_settings: dict[str, Any] = {
        "version": 2,
        "auth": auth or client_uuid,
        "up": up if up is not None else HYSTERIA_UP,
        "down": down if down is not None else HYSTERIA_DOWN,
        "congestion": "bbr",
    }
    return {
        "protocol": "hysteria",
        "settings": {
            "version": 2,
            "address": host,
            "port": int(port),
        },
        "streamSettings": {
            "network": "hysteria",
            "security": "tls",
            "tlsSettings": {
                "allowInsecure": False,
                "alpn": alpn or HYSTERIA_ALPN or ["h3"],
                "serverName": sni,
            },
            "hysteriaSettings": hysteria_settings,
        },
        "tag": tag,
    }


def build_hysteria2_uri(
    client_uuid: str,
    *,
    host: Optional[str] = None,
    port: Optional[int] = None,
    sni: Optional[str] = None,
    remark: Optional[str] = None,
) -> str:
    """hy2:// URI для Happ / INCY (параллельно JSON-профилю)."""
    h = host or HYSTERIA_PUBLIC_HOST
    p = int(port or HYSTERIA_PORT)
    server_name = sni or HYSTERIA_SNI or h
    name = urllib.parse.quote(remark or PROFILE_HYSTERIA_LTE)
    qs = urllib.parse.urlencode(
        {
            "sni": server_name,
            "insecure": "0",
            "alpn": ",".join(HYSTERIA_ALPN or ["h3"]),
        }
    )
    return f"hy2://{urllib.parse.quote(client_uuid, safe='')}@{h}:{p}?{qs}#{name}"


def build_hysteria_lte_config(
    client_uuid: str,
    base_remark: str = COUNTRY_LABEL,
    *,
    host: Optional[str] = None,
    port: Optional[int] = None,
    sni: Optional[str] = None,
    display_name: Optional[str] = None,
    user_id: Optional[int] = None,
    **_: Any,
) -> dict[str, Any]:
    """Hysteria2 UDP/QUIC — лучше на LTE/4G при потере пакетов; auth = VLESS UUID."""
    _ = base_remark
    h = host or HYSTERIA_PUBLIC_HOST
    p = int(port or HYSTERIA_PORT)
    server_name = sni or HYSTERIA_SNI or h
    remark = display_name or PROFILE_HYSTERIA_LTE
    outbound = _hysteria2_outbound(
        client_uuid,
        host=h,
        port=p,
        sni=server_name,
        auth=client_uuid,
    )
    return _base_config(
        remark,
        outbound,
        meta=_happ_meta(
            user_id=user_id,
            extra={
                "serverDescription": "Hysteria2 · UDP/QUIC · BBR · LTE / 4G / слабый сигнал",
            },
        ),
        routing=_ultima_routing_rules(),
        dns_servers=["8.8.8.8", "8.8.4.4"],
    )


def build_info_stub_config(remark: str, *, description: str = "", expired: bool = True) -> dict[str, Any]:
    """Инфо-узел как у UltimaVPN (не для подключения)."""
    outbound: dict[str, Any] = {
        "protocol": "vless",
        "settings": {
            "vnext": [
                {
                    "address": "127.0.0.1",
                    "port": 1,
                    "users": [
                        {
                            "encryption": "none",
                            "flow": "",
                            "id": "00000000-0000-0000-0000-000000000001",
                        }
                    ],
                }
            ]
        },
        "streamSettings": {"network": "tcp", "security": "none"},
        "tag": "proxy",
    }
    meta = _happ_meta(expired=expired, extra={"serverDescription": description[:200] if description else ""})
    return _base_config(remark, outbound, meta=meta)


def build_auto_balancer_config(
    client_uuid: str,
    base_remark: str = COUNTRY_LABEL,
    *,
    host: Optional[str] = None,
    grpc_port: Optional[int] = None,
    xhttp_host: Optional[str] = None,
    xhttp_port: Optional[int] = None,
    xhttp_path: Optional[str] = None,
    tcp_port: Optional[int] = None,
    sni: Optional[str] = None,
    tcp_sni: Optional[str] = None,
    pbk: Optional[str] = None,
    sid: Optional[str] = None,
    service_name: Optional[str] = None,
    grpc_fingerprint: Optional[str] = None,
    tcp_fingerprint: Optional[str] = None,
    xhttp_fingerprint: Optional[str] = None,
    display_name: Optional[str] = None,
    user_id: Optional[int] = None,
) -> dict[str, Any]:
    """
    Auto как у UltimaVPN: один TCP Reality :443 (SNI hh.ru) + fragment.
    Несколько outbound без balancer ломали Happ на части устройств.
    """
    remark = display_name or PROFILE_AUTO
    outbound = _tcp_outbound(
        client_uuid,
        host=host or PUBLIC_HOST,
        port=int(tcp_port or TCP_PORT),
        sni=WHITELIST_SNI,
        pbk=pbk or REALITY_PBK,
        sid=sid or REALITY_SID,
        fingerprint=tcp_fingerprint or TCP_REALITY_FP or "firefox",
        flow=TCP_VLESS_FLOW,
        with_fragment=True,
        tag="proxy",
    )
    return _base_config(
        remark,
        outbound,
        meta=_happ_meta(
            user_id=user_id,
            extra={
                "serverDescription": "VLESS | TCP | Reality | :443 | SNI hh.ru",
            },
        ),
        routing=_ultima_routing_rules(),
        dns={"queryStrategy": "UseIP", "servers": ["8.8.8.8", "8.8.4.4"]},
        route_only=False,
    )


def build_grpc_turbo_config(
    client_uuid: str,
    base_remark: str = COUNTRY_LABEL,
    *,
    host: Optional[str] = None,
    port: Optional[int] = None,
    sni: Optional[str] = None,
    pbk: Optional[str] = None,
    sid: Optional[str] = None,
    service_name: Optional[str] = None,
    fingerprint: Optional[str] = None,
    display_name: Optional[str] = None,
    user_id: Optional[int] = None,
) -> dict[str, Any]:
    remark = display_name or PROFILE_TURBO
    outbound = _grpc_turbo_outbound(
        client_uuid,
        host=host or PUBLIC_HOST,
        port=int(port or GRPC_PORT),
        sni=sni or REALITY_SNI,
        pbk=pbk or REALITY_PBK,
        sid=sid or REALITY_SID,
        service_name=service_name or GRPC_SERVICE,
        fingerprint=GRPC_TURBO_FP or "chrome",
    )
    return _base_config(
        remark,
        outbound,
        meta=_happ_meta(
            user_id=user_id,
            extra={"serverDescription": "VLESS | gRPC | Reality · максимальная скорость"},
        ),
        routing=_ultima_routing_rules(),
        dns_servers=["8.8.8.8", "8.8.4.4"],
    )


def build_grpc_fast_config(
    client_uuid: str,
    base_remark: str = COUNTRY_LABEL,
    *,
    host: Optional[str] = None,
    port: Optional[int] = None,
    sni: Optional[str] = None,
    pbk: Optional[str] = None,
    sid: Optional[str] = None,
    service_name: Optional[str] = None,
    fingerprint: Optional[str] = None,
    display_name: Optional[str] = None,
    user_id: Optional[int] = None,
) -> dict[str, Any]:
    remark = display_name or _display_name(PROFILE_FAST, country=_clean_remark(base_remark))
    outbound = _grpc_outbound(
        client_uuid,
        host=host or PUBLIC_HOST,
        port=int(port or GRPC_PORT),
        sni=sni or REALITY_SNI,
        pbk=pbk or REALITY_PBK,
        sid=sid or REALITY_SID,
        service_name=service_name or GRPC_SERVICE,
        fingerprint=fingerprint or REALITY_FP,
        with_fragment=True,
    )
    return _base_config(remark, outbound, meta=_happ_meta(user_id=user_id))


def build_grpc_antiblock_config(
    client_uuid: str,
    base_remark: str = COUNTRY_LABEL,
    *,
    host: Optional[str] = None,
    pbk: Optional[str] = None,
    sid: Optional[str] = None,
    display_name: Optional[str] = None,
    user_id: Optional[int] = None,
    **_: Any,
) -> dict[str, Any]:
    """gRPC :8443 как «Быстрый» — стабильно в Happ iOS; chrome fp для LTE."""
    remark = display_name or _display_name(PROFILE_ANTIBLOCK, country=_clean_remark(base_remark))
    outbound = _grpc_outbound(
        client_uuid,
        host=host or PUBLIC_HOST,
        port=int(GRPC_PORT),
        sni=REALITY_SNI,
        pbk=pbk or REALITY_PBK,
        sid=sid or REALITY_SID,
        service_name=GRPC_SERVICE,
        fingerprint=GRPC_TURBO_FP or "chrome",
        with_fragment=True,
    )
    return _base_config(
        remark,
        outbound,
        meta=_happ_meta(
            user_id=user_id,
            extra={"serverDescription": "VLESS | gRPC | Reality · LTE / Мегафон / 4G"},
        ),
        routing=_routing_rules(),
        dns_servers=["8.8.8.8", "8.8.4.4"],
    )


def build_youtube_balancer_config(
    client_uuid: str,
    base_remark: str = COUNTRY_LABEL,
    *,
    host: Optional[str] = None,
    grpc_port: Optional[int] = None,
    xhttp_host: Optional[str] = None,
    xhttp_port: Optional[int] = None,
    xhttp_path: Optional[str] = None,
    tcp_port: Optional[int] = None,
    sni: Optional[str] = None,
    tcp_sni: Optional[str] = None,
    pbk: Optional[str] = None,
    sid: Optional[str] = None,
    service_name: Optional[str] = None,
    grpc_fingerprint: Optional[str] = None,
    tcp_fingerprint: Optional[str] = None,
    xhttp_fingerprint: Optional[str] = None,
    display_name: Optional[str] = None,
    user_id: Optional[int] = None,
) -> dict[str, Any]:
    """
    YouTube-профиль: burstObservatory + leastLoad balancer (gRPC / XHTTP / TCP Vision).
    RU direct, реклама block, YouTube/Google через балансер.
    Полная блокировка рекламы без Premium невозможна на клиенте — см. _youtube_ad_block_domains.
    """
    remark = display_name or PROFILE_YOUTUBE
    grpc_host = host or PUBLIC_HOST
    x_host = xhttp_host or XHTTP_PUBLIC_HOST
    reality_sni = sni or REALITY_SNI
    reality_pbk = pbk or REALITY_PBK
    reality_sid = sid or REALITY_SID
    outbounds = [
        _tcp_outbound(
            client_uuid,
            host=grpc_host,
            port=int(tcp_port or TCP_PORT),
            sni=WHITELIST_SNI,
            pbk=reality_pbk,
            sid=reality_sid,
            fingerprint=tcp_fingerprint or TCP_REALITY_FP or "firefox",
            flow=TCP_VLESS_FLOW,
            with_fragment=True,
            tag="pr_YT_TCP",
        ),
        _grpc_outbound(
            client_uuid,
            host=grpc_host,
            port=int(grpc_port or GRPC_PORT),
            sni=reality_sni,
            pbk=reality_pbk,
            sid=reality_sid,
            service_name=service_name or GRPC_SERVICE,
            fingerprint=grpc_fingerprint or GRPC_TURBO_FP or "chrome",
            with_fragment=True,
            tag="pr_YT_GRPC",
        ),
        _xhttp_outbound(
            client_uuid,
            host=x_host,
            port=int(xhttp_port or XHTTP_PORT),
            path=xhttp_path or XHTTP_PATH,
            fingerprint=xhttp_fingerprint or XHTTP_FINGERPRINT,
            tag="pr_YT_XHTTP",
        ),
    ]
    return _balancer_config(
        remark,
        outbounds,
        meta=_happ_meta(
            user_id=user_id,
            extra={
                "serverDescription": (
                    "YouTube/Google через VPN · реклама block · RU direct · "
                    "снижает рекламу, 100% только с Premium"
                ),
            },
        ),
        routing=_ultima_routing_rules(),
        dns={"queryStrategy": "UseIP", "servers": ["8.8.8.8", "8.8.4.4"]},
        burst_observatory=None,
        route_only=False,
    )


def build_youtube_config(
    client_uuid: str,
    base_remark: str = COUNTRY_LABEL,
    *,
    host: Optional[str] = None,
    port: Optional[int] = None,
    sni: Optional[str] = None,
    pbk: Optional[str] = None,
    sid: Optional[str] = None,
    service_name: Optional[str] = None,
    fingerprint: Optional[str] = None,
    display_name: Optional[str] = None,
    user_id: Optional[int] = None,
) -> dict[str, Any]:
    """YouTube-профиль в стиле Ultima: один TCP Reality + fragment, простой RU-direct."""
    remark = display_name or PROFILE_YOUTUBE
    # Важно: nginx stream :443 пропускает только SNI hh.ru → xray:10443.
    # SNI из vless-ссылки (www.apple.com) ломает TCP-профили.
    outbound = _tcp_outbound(
        client_uuid,
        host=host or PUBLIC_HOST,
        port=int(port or TCP_PORT),
        sni=WHITELIST_SNI,
        pbk=pbk or REALITY_PBK,
        sid=sid or REALITY_SID,
        fingerprint=fingerprint or TCP_REALITY_FP or "firefox",
        flow=TCP_VLESS_FLOW,
        with_fragment=True,
        tag="proxy",
    )
    return _base_config(
        remark,
        outbound,
        meta=_happ_meta(
            user_id=user_id,
            extra={"serverDescription": "YouTube · TCP Reality · без fragment"},
        ),
        routing=_ultima_routing_rules(),
        dns={"queryStrategy": "UseIP", "servers": ["8.8.8.8", "8.8.4.4"]},
        route_only=False,
    )


def build_xhttp_lte_config(
    client_uuid: str,
    base_remark: str = COUNTRY_LABEL,
    *,
    host: Optional[str] = None,
    port: Optional[int] = None,
    path: Optional[str] = None,
    fingerprint: Optional[str] = None,
    display_name: Optional[str] = None,
    user_id: Optional[int] = None,
    **_: Any,
) -> dict[str, Any]:
    """VLESS + XHTTP + TLS на :443 — обход LTE (Megafon/4G), split-tunnel."""
    host = host or XHTTP_PUBLIC_HOST
    remark = display_name or PROFILE_XHTTP_LTE
    outbound = _xhttp_outbound(
        client_uuid,
        host=host,
        port=int(port or XHTTP_PORT),
        path=path or XHTTP_PATH,
        fingerprint=fingerprint or XHTTP_FINGERPRINT,
    )
    return _base_config(
        remark,
        outbound,
        meta=_happ_meta(
            user_id=user_id,
            extra={"serverDescription": "LTE · Мегафон · 4G · split-tunnel"},
        ),
        routing=_ultima_routing_rules(),
        dns_servers=["8.8.8.8", "8.8.4.4"],
    )


def build_cloudflare_ws_config(
    client_uuid: str,
    base_remark: str = COUNTRY_LABEL,
    *,
    host: Optional[str] = None,
    port: Optional[int] = None,
    path: Optional[str] = None,
    sni: Optional[str] = None,
    fingerprint: Optional[str] = None,
    display_name: Optional[str] = None,
    user_id: Optional[int] = None,
    **_: Any,
) -> dict[str, Any]:
    """VLESS + WebSocket + TLS через Cloudflare (proxied cf.*).
    Клиент коннектится к anycast-IP Cloudflare, а не к IP сервера, поэтому
    IP-блокировка сервера российскими операторами обходится, а SNI остаётся чистым."""
    host = host or CF_WS_HOST
    remark = display_name or PROFILE_CF
    outbound = _ws_outbound(
        client_uuid,
        host=host,
        port=int(port or CF_WS_PORT),
        path=path or CF_WS_PATH,
        sni=sni or CF_WS_SNI,
        fingerprint=fingerprint or CF_WS_FP,
    )
    return _base_config(
        remark,
        outbound,
        meta=_happ_meta(
            user_id=user_id,
            extra={"serverDescription": "☁️ Cloudflare · обход блокировок · стабильно на мобильных"},
        ),
        routing=_ultima_routing_rules(),
        dns_servers=["8.8.8.8", "8.8.4.4"],
    )


def build_whitelist_lte_config(
    client_uuid: str,
    base_remark: str = COUNTRY_LABEL,
    *,
    host: Optional[str] = None,
    port: Optional[int] = None,
    sni: Optional[str] = None,
    pbk: Optional[str] = None,
    sid: Optional[str] = None,
    fingerprint: Optional[str] = None,
    display_name: Optional[str] = None,
    user_id: Optional[int] = None,
) -> dict[str, Any]:
    remark = display_name or PROFILE_WHITELIST
    outbound = _tcp_outbound(
        client_uuid,
        host=host or PUBLIC_HOST,
        port=int(port or TCP_PORT),
        sni=WHITELIST_SNI,
        pbk=pbk or REALITY_PBK,
        sid=sid or REALITY_SID,
        fingerprint=fingerprint or TCP_REALITY_FP or "firefox",
        flow=TCP_VLESS_FLOW,
        with_fragment=True,
    )
    return _base_config(
        remark,
        outbound,
        meta=_happ_meta(
            user_id=user_id,
            extra={"serverDescription": "VLESS | TCP | Reality | JSON · LTE белые списки"},
        ),
        routing=_whitelist_routing_rules(),
        dns_servers=["8.8.8.8", "8.8.4.4"],
    )


# обратная совместимость
build_tcp_mobile_config = build_whitelist_lte_config


def build_expired_subscription(user_id: Optional[int] = None) -> list[dict[str, Any]]:
    bot_label = f"@{BOT_USERNAME} в Telegram"
    return [
        build_info_stub_config("⛔ Ваша подписка истекла", description="Срок действия ключа закончился"),
        build_info_stub_config("Продлите доступ через бот", description=BOT_TELEGRAM_URL),
        build_info_stub_config(bot_label, description="Откройте бота и выберите тариф"),
    ]


def build_happ_json_subscription(
    vless_link: str,
    *,
    user_id: Optional[int] = None,
    email: Optional[str] = None,
    expires_at: Optional[str] = None,
) -> list[dict[str, Any]]:
    if is_expired(expires_at):
        return build_expired_subscription(user_id)

    p = parse_vless_link(vless_link)
    uuid = p.get("uuid") or ""
    if not uuid:
        raise ValueError("invalid vless link: no uuid")
    country = _clean_remark(p.get("remark") or COUNTRY_LABEL)
    common = {
        "sni": p.get("sni") or None,
        "pbk": p.get("pbk") or None,
        "sid": p.get("sid") or None,
        "fingerprint": p.get("fp") or None,
        "user_id": user_id,
    }
    profiles = [
        # 0) Cloudflare WS (proxied) — обход блокировки IP сервера в РФ. Первый = приоритетный.
        build_cloudflare_ws_config(uuid, country, user_id=user_id),
        # 1) TCP Reality :443 (белые списки / hh.ru) — без fragment (nginx ssl_preread)
        build_auto_balancer_config(
            uuid,
            country,
            user_id=user_id,
            host=PUBLIC_HOST,
            pbk=common.get("pbk"),
            sid=common.get("sid"),
            sni=common.get("sni") or REALITY_SNI,
            grpc_fingerprint=common.get("fingerprint"),
        ),
        # 2) XHTTP :8445 — запасной LTE-обход (не за nginx preread)
        build_xhttp_lte_config(uuid, country, user_id=user_id, host=XHTTP_PUBLIC_HOST),
        build_whitelist_lte_config(
            uuid,
            country,
            user_id=user_id,
            host=PUBLIC_HOST,
            pbk=common.get("pbk"),
            sid=common.get("sid"),
        ),
        build_hysteria_lte_config(
            uuid,
            country,
            user_id=user_id,
            host=HYSTERIA_PUBLIC_HOST,
        ),
        build_grpc_turbo_config(
            uuid,
            country,
            user_id=user_id,
            host=PUBLIC_HOST,
            pbk=common.get("pbk"),
            sid=common.get("sid"),
            sni=common.get("sni") or REALITY_SNI,
        ),
        build_grpc_fast_config(uuid, country, **common),
        build_grpc_antiblock_config(
            uuid,
            country,
            user_id=user_id,
            host=PUBLIC_HOST,
            pbk=common.get("pbk"),
            sid=common.get("sid"),
        ),
        build_youtube_config(
            uuid,
            country,
            user_id=user_id,
            host=PUBLIC_HOST,
            pbk=common.get("pbk"),
            sid=common.get("sid"),
            # TCP :443 Reality — только hh.ru (не SNI из gRPC vless)
            sni=None,
            fingerprint=common.get("fingerprint"),
        ),
    ]
    return profiles


def build_happ_json_subscription_from_vless(vless_link: str) -> list[dict[str, Any]]:
    """Обратная совместимость."""
    return build_happ_json_subscription(vless_link)


def subscription_userinfo(
    *,
    upload: int = 0,
    download: int = 0,
    expire_ts: Optional[int] = None,
) -> str:
    exp = expire_ts or 0
    return f"upload={upload}; download={download}; total=0; expire={exp}"


def json_subscription_enabled() -> bool:
    return SUBSCRIPTION_FORMAT in ("json", "1", "true", "yes")
