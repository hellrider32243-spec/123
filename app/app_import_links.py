"""Deep links и HTTPS-импорт подписки в Happ / INCY."""
from __future__ import annotations

import html as html_lib
import os
import urllib.parse
from typing import Literal

AppName = Literal["happ", "incy"]

HAPP_SCHEME = os.getenv("HAPP_SCHEME", "happ://").strip()
INCY_SCHEME = os.getenv("INCY_SCHEME", "incy://").strip()
VPN_PROFILE_NAME = os.getenv("VPN_PROFILE_NAME", "TritonVPN").strip() or "TritonVPN"
# JSON-подписка уже содержит fragment внутри конфигов.
# Дописывать ?fragment= ПОСЛЕ #Profile ломает импорт в Happ (Android/iOS):
# имя профиля становится "TritonVPN?fragment=..." и подписка не добавляется.
# По умолчанию выключено. Включать только для старых plaintext-подписок.
HAPP_FRAGMENT = os.getenv("HAPP_FRAGMENT", "").strip()
HAPP_DEEP_LINK_FRAGMENT = os.getenv("HAPP_DEEP_LINK_FRAGMENT", "").strip().lower() in (
    "1",
    "true",
    "yes",
)
SUBSCRIPTION_FORMAT = os.getenv("SUBSCRIPTION_FORMAT", "json").strip().lower()

INCY_IOS_URL = os.getenv(
    "INCY_IOS_URL",
    "https://apps.apple.com/ru/app/incy/id6756943388",
).strip()
INCY_ANDROID_URL = os.getenv(
    "INCY_ANDROID_URL",
    "https://play.google.com/store/apps/details?id=llc.itdev.incy",
).strip()

HAPP_IOS_URL = os.getenv(
    "HAPP_IOS_URL",
    "https://apps.apple.com/ru/app/happ-proxy-utility-plus/id6746188973",
).strip()
HAPP_ANDROID_URL = os.getenv(
    "HAPP_ANDROID_URL",
    "https://play.google.com/store/apps/details?id=com.happproxy",
).strip()
HAPP_ANDROID_PACKAGE = os.getenv("HAPP_ANDROID_PACKAGE", "com.happproxy").strip()


def _scheme_prefix(scheme: str) -> str:
    return scheme if scheme.endswith("://") else f"{scheme}://"


def subscription_fetch_url(subscription_url: str) -> str:
    """HTTP-часть без #profile (хэш не уходит на сервер)."""
    trimmed = (subscription_url or "").strip()
    if "#" in trimmed:
        trimmed = trimmed.split("#", 1)[0]
    return trimmed


def sanitize_subscription_url(url: str) -> str:
    if not url:
        raise ValueError("empty subscription_url")
    trimmed = subscription_fetch_url(url)
    if not (trimmed.startswith("http://") or trimmed.startswith("https://")):
        raise ValueError("subscription_url must be http(s)")
    if any(ch in trimmed for ch in (" ", "#", "\n", "\r", "\t")):
        raise ValueError("subscription_url contains forbidden characters")
    return trimmed


def build_happ_deep_link(
    subscription_url: str,
    *,
    profile_name: str | None = None,
    fragment: str | None = None,
) -> str:
    """happ://add/<https-url>#Profile

    Важно: НЕ дописывать ?fragment= после # — Happ воспринимает всё после #
    как имя профиля, и импорт на Android/iOS ломается.
    """
    clean = sanitize_subscription_url(subscription_url)
    profile = urllib.parse.quote(profile_name or VPN_PROFILE_NAME, safe="")
    scheme = _scheme_prefix(HAPP_SCHEME)
    link = f"{scheme}add/{clean}#{profile}"

    # Только если явно разрешили deep-link fragment И формат не JSON.
    use_frag = fragment if fragment is not None else (
        HAPP_FRAGMENT if HAPP_DEEP_LINK_FRAGMENT and SUBSCRIPTION_FORMAT not in ("json", "1", "true", "yes") else ""
    )
    if use_frag:
        # Корректнее класть ДО hash, но Happ это не документирует —
        # безопаснее просто не добавлять при JSON.
        frag_q = urllib.parse.quote(use_frag, safe=",-")
        link = f"{scheme}add/{clean}?fragment={frag_q}#{profile}"
    return link


def build_incy_deep_link(subscription_url: str) -> str:
    clean = sanitize_subscription_url(subscription_url)
    scheme = _scheme_prefix(INCY_SCHEME)
    return f"{scheme}add/{clean}"


def build_app_deep_link(subscription_url: str, app: AppName = "happ") -> str:
    if app == "incy":
        return build_incy_deep_link(subscription_url)
    return build_happ_deep_link(subscription_url)


def build_android_intent_link(subscription_url: str, *, profile_name: str | None = None) -> str:
    """Android Intent URL — лучше открывается из WebView Telegram, чем сырой happ://."""
    clean = sanitize_subscription_url(subscription_url)
    profile = urllib.parse.quote(profile_name or VPN_PROFILE_NAME, safe="")
    # path после intent:// ; #TritonVPN нельзя — сломает #Intent
    # Поэтому профиль передаём только в fallback https URL, а deep path без hash.
    path = f"add/{clean}"
    fallback = urllib.parse.quote(
        f"{clean}?action=add&app=happ#{profile_name or VPN_PROFILE_NAME}",
        safe="",
    )
    return (
        f"intent://{path}#Intent;"
        f"scheme=happ;package={HAPP_ANDROID_PACKAGE};"
        f"S.browser_fallback_url={fallback};end"
    )


def subscription_import_https_url(subscription_url: str, app: AppName = "happ") -> str:
    """HTTPS-ссылка для кнопок Telegram (?action=add&app=...)."""
    base = sanitize_subscription_url(subscription_url)
    sep = "&" if "?" in base else "?"
    profile_suffix = ""
    raw = (subscription_url or "").strip()
    if "#" in raw:
        profile_suffix = "#" + raw.split("#", 1)[1]
    return f"{base}{sep}action=add&app={app}{profile_suffix}"


def app_import_redirect_html(deep_link: str, app: AppName, *, sub_url: str = "") -> str:
    title = "INCY" if app == "incy" else "Happ"
    store_ios = INCY_IOS_URL if app == "incy" else HAPP_IOS_URL
    store_android = INCY_ANDROID_URL if app == "incy" else HAPP_ANDROID_URL

    clean_sub = ""
    profile = VPN_PROFILE_NAME
    if "add/" in (deep_link or ""):
        rest = deep_link.split("add/", 1)[-1]
        clean_sub = rest.split("#", 1)[0].split("?", 1)[0]
        if "#" in rest:
            profile = urllib.parse.unquote(rest.split("#", 1)[1].split("?", 1)[0])
    if not clean_sub and sub_url:
        clean_sub = subscription_fetch_url(sub_url)
        if "#" in (sub_url or ""):
            profile = sub_url.split("#", 1)[1].split("?", 1)[0]

    # Полная ссылка для копирования (с #Profile) — Happ так надёжнее импортирует.
    copy_sub = f"{clean_sub}#{profile}" if clean_sub else clean_sub

    intent_link = ""
    if app == "happ" and clean_sub:
        try:
            intent_link = build_android_intent_link(clean_sub, profile_name=profile)
        except Exception:
            intent_link = ""

    # Нормализуем deep link: без хвоста ?fragment= после #
    if deep_link and "#TritonVPN?fragment=" in deep_link:
        deep_link = deep_link.split("?fragment=", 1)[0]
    if deep_link and "?fragment=" in deep_link and deep_link.rfind("#") < deep_link.rfind("?fragment="):
        # strip broken suffix after hash
        hash_i = deep_link.find("#")
        if hash_i >= 0:
            after = deep_link[hash_i + 1 :]
            deep_link = deep_link[: hash_i + 1] + after.split("?", 1)[0]

    safe_deep = html_lib.escape(deep_link, quote=True)
    safe_intent = html_lib.escape(intent_link, quote=True)
    safe_sub = html_lib.escape(copy_sub, quote=True)
    js_deep = deep_link.replace("\\", "\\\\").replace("'", "\\'")
    js_intent = intent_link.replace("\\", "\\\\").replace("'", "\\'")
    js_sub = copy_sub.replace("\\", "\\\\").replace("'", "\\'")
    safe_ios = html_lib.escape(store_ios, quote=True)
    safe_and = html_lib.escape(store_android, quote=True)

    return f"""<!doctype html>
<html lang="ru"><head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<title>Добавить в {title}</title>
<style>
  body{{font-family:-apple-system,BlinkMacSystemFont,sans-serif;background:#0b1220;color:#f0f6ff;margin:0;min-height:100vh;display:flex;align-items:center;justify-content:center}}
  .card{{text-align:center;padding:28px 20px;max-width:460px;width:100%;box-sizing:border-box}}
  h2{{font-size:22px;margin:0 0 12px;color:#64f4c8}}
  p{{color:rgba(240,246,255,.8);line-height:1.5;font-size:15px;margin:0 0 10px}}
  .hint{{font-size:13px;color:rgba(240,246,255,.55);margin-top:14px}}
  a.btn,button.btn{{display:block;margin:14px auto 0;padding:16px 24px;max-width:320px;background:linear-gradient(135deg,#00d4ff,#64f4c8);color:#021a10;font-weight:800;text-decoration:none;border-radius:14px;border:0;font-size:17px;cursor:pointer}}
  button.sec,a.sec{{display:inline-block;margin-top:14px;color:#8fdfff;font-size:14px;background:transparent;border:0;text-decoration:underline;cursor:pointer}}
  code{{display:block;margin-top:16px;padding:12px;background:rgba(255,255,255,.06);border-radius:12px;word-break:break-all;font-size:12px;color:#cfefff;text-align:left}}
  .ok{{color:#64f4c8;font-size:13px;min-height:18px;margin-top:8px}}
  .warn{{color:#ffcc66;font-size:13px;margin-top:8px}}
</style>
</head>
<body>
<div class="card">
  <h2>Добавить TritonVPN в {title}</h2>
  <p id="howto"><b>Android:</b> нажмите зелёную кнопку.<br>
     Если не открылось — ⋮ / «Открыть в Chrome», затем снова кнопку.<br><br>
     <b>iPhone:</b> нажмите «…» → Safari → снова «Открыть {title}».</p>
  <a class="btn" id="openBtn" href="{safe_deep}">Открыть {title}</a>
  <button class="btn" id="copyBtn" type="button" style="background:#1c2a44;color:#64f4c8;margin-top:10px">Скопировать ссылку</button>
  <p class="ok" id="status"></p>
  <p class="warn" id="tgHint" style="display:none">Откройте эту страницу во внешнем браузере — внутри Telegram кнопки часто не срабатывают.</p>
  <code id="subUrl">{safe_sub}</code>
  <p class="hint">Запасной способ: скопируйте ссылку → {title} → ＋ → «Из буфера».<br>
     Профили: 🇳🇱 Нидерланды · 🇳🇱 Нидерланды #2 · 🇪🇺 Hysteria</p>
  <a class="sec" href="{safe_ios}">Скачать {title} (iOS)</a><br>
  <a class="sec" href="{safe_and}">Скачать {title} (Android)</a>
</div>
<iframe id="fr" style="display:none;width:0;height:0;border:0"></iframe>
<script>
  var deep = '{js_deep}';
  var intent = '{js_intent}';
  var sub = '{js_sub}';
  var ua = navigator.userAgent || '';
  var isAndroid = /Android/i.test(ua);
  var isIOS = /iPhone|iPad|iPod/i.test(ua);
  var inTG = /Telegram/i.test(ua);
  if (inTG) {{ document.getElementById('tgHint').style.display = 'block'; }}
  function tryOpen() {{
    var url = (isAndroid && intent) ? intent : deep;
    try {{ document.getElementById('fr').src = url; }} catch (e) {{}}
    try {{ window.location.href = url; }} catch (e2) {{}}
    // iOS fallback: повтор сырого happ://
    if (isIOS) {{
      setTimeout(function() {{ try {{ window.location.href = deep; }} catch (e3) {{}} }}, 500);
    }}
  }}
  document.getElementById('openBtn').addEventListener('click', function(e) {{
    e.preventDefault();
    tryOpen();
    setTimeout(tryOpen, 350);
  }});
  document.getElementById('copyBtn').addEventListener('click', async function() {{
    try {{
      if (navigator.clipboard && navigator.clipboard.writeText) {{
        await navigator.clipboard.writeText(sub);
      }} else {{
        var ta = document.createElement('textarea');
        ta.value = sub; document.body.appendChild(ta); ta.select();
        document.execCommand('copy'); document.body.removeChild(ta);
      }}
      document.getElementById('status').textContent = 'Скопировано! Откройте {title} → ＋ → из буфера';
    }} catch (e) {{
      document.getElementById('status').textContent = 'Скопируйте ссылку вручную из поля выше';
    }}
  }});
  // Вне Telegram — автозапуск; внутри TG на Android тоже пробуем intent
  if (!inTG) {{
    setTimeout(tryOpen, 250);
  }} else if (isAndroid && intent) {{
    setTimeout(tryOpen, 400);
  }}
</script>
</body></html>"""
