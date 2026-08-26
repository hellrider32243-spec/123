#!/usr/bin/env python3
"""Перевыпуск ссылок подписки: старый vless wingsvpn.shop:8443 → NL Reality.

Срок и UUID те же. Пишет новую HTTPS-ссылку в Telegram.

  python3 infra/reissue_ams_subscription_links.py --dry-run
  python3 infra/reissue_ams_subscription_links.py --send
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import sqlite3
import time
import urllib.error
import urllib.parse
import urllib.request
import http.cookiejar
from datetime import datetime, timezone
from pathlib import Path

ENV_FILE = Path(os.getenv("NORDWINGS_ENV", "/opt/nordwings/app/.env"))
BOT_DB = Path(os.getenv("DB_PATH", "/opt/3xui-bot/bot.db"))
XUI_DB = Path("/etc/x-ui/x-ui.db")
SUB_BASE = "https://ams.wingsvpn.shop/miniapp/sub"
PROFILE = "TritonVPN"


def load_env(path: Path) -> dict[str, str]:
    out: dict[str, str] = {}
    if not path.exists():
        return out
    for raw in path.read_text().splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        out[k.strip()] = v.strip()
    return out


def parse_dt(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(str(value))
    except Exception:
        return None
    if dt.tzinfo is not None:
        dt = dt.astimezone().replace(tzinfo=None)
    return dt


def uuid_from_vless(link: str) -> str:
    m = re.search(r"vless://([^@/]+)", link or "")
    return (m.group(1) if m else "").strip()


def parse_vless(link: str) -> dict:
    m = re.search(r"vless://([^@/]+)@([^:]+):(\d+)\?([^#]*)", link or "")
    if not m:
        return {}
    qs = urllib.parse.parse_qs(m.group(4))
    return {
        "uuid": m.group(1),
        "host": m.group(2),
        "port": m.group(3),
        "sni": (qs.get("sni") or [""])[0],
        "type": (qs.get("type") or [""])[0],
    }


def sanitize_email(email: str, uuid: str) -> str:
    s = "".join(ch if ch.isascii() and (ch.isalnum() or ch in "._-") else "_" for ch in (email or ""))
    s = re.sub(r"_+", "_", s).strip("._-")[:60]
    return s or ("u_" + uuid.split("-")[0])


def vless_is_new(pv: dict) -> bool:
    return (
        pv.get("host") == "139.28.240.160"
        and pv.get("port") == "443"
        and pv.get("sni") == "deepl.com"
    )


def make_vless(uuid: str, email: str, env: dict) -> str:
    host = env.get("PUBLIC_VLESS_HOST") or env.get("AMS_HOST") or "139.28.240.160"
    port = int(env.get("PUBLIC_VLESS_PORT") or env.get("AMS_PORT") or "443")
    sni = env.get("AMS_SNI") or env.get("SNI") or "deepl.com"
    pbk = env.get("AMS_PBK") or env.get("REALITY_PBK") or ""
    sid = env.get("AMS_SID") or env.get("REALITY_SID") or ""
    fp = env.get("AMS_FP") or env.get("REALITY_FP") or "safari"
    flow = env.get("AMS_FLOW") or env.get("VLESS_FLOW") or "xtls-rprx-vision"
    qemail = urllib.parse.quote(email)
    return (
        f"vless://{uuid}@{host}:{port}"
        f"?type=tcp&security=reality&sni={urllib.parse.quote(sni, safe='')}"
        f"&fp={urllib.parse.quote(fp, safe='')}&pbk={urllib.parse.quote(pbk, safe='')}"
        f"&sid={urllib.parse.quote(sid, safe='')}&spx=%2F&encryption=none"
        f"&flow={urllib.parse.quote(flow, safe='')}#{qemail}"
    )


def sub_url(user_id: int) -> str:
    return f"{SUB_BASE}/{user_id}#{PROFILE}"


def import_https(user_id: int, app: str) -> str:
    return f"{SUB_BASE}/{user_id}?action=add&app={app}#{PROFILE}"


def fmt_exp(dt: datetime | None) -> str:
    if not dt:
        return "—"
    return dt.strftime("%d.%m.%Y %H:%M")


def tg_send(token: str, chat_id: int, text: str, markup: dict) -> tuple[int, str]:
    body = urllib.parse.urlencode(
        {
            "chat_id": chat_id,
            "text": text,
            "parse_mode": "HTML",
            "disable_web_page_preview": "true",
            "reply_markup": json.dumps(markup, ensure_ascii=False),
        }
    ).encode()
    req = urllib.request.Request(
        f"https://api.telegram.org/bot{token}/sendMessage",
        data=body,
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            raw = resp.read().decode()
            data = json.loads(raw)
            if data.get("ok"):
                return 200, "ok"
            return 400, str(data)[:200]
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()[:300]


def panel_login(env: dict):
    user = env.get("XUI_USERNAME") or "triton"
    pw = env.get("XUI_PASSWORD") or ""
    base = (env.get("BASE_URL") or "http://127.0.0.1:2053/panel").rstrip("/")
    # BASE_URL is http://127.0.0.1:2053/panel → origin http://127.0.0.1:2053
    origin = base[: base.find("/panel")] if "/panel" in base else "http://127.0.0.1:2053"
    cj = http.cookiejar.CookieJar()
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))
    html = opener.open(origin + "/panel/", timeout=10).read().decode()
    m = re.search(r'name="csrf-token" content="([^"]+)"', html)
    csrf = m.group(1) if m else ""
    req = urllib.request.Request(
        origin + "/panel/login",
        data=json.dumps({"username": user, "password": pw}).encode(),
        headers={
            "Content-Type": "application/json",
            "X-CSRF-Token": csrf,
            "X-Requested-With": "XMLHttpRequest",
        },
        method="POST",
    )
    out = json.loads(opener.open(req, timeout=10).read().decode())
    if not out.get("success"):
        raise SystemExit(f"x-ui login failed: {out}")
    html2 = opener.open(origin + "/panel/panel/", timeout=10).read().decode()
    m2 = re.search(r'name="csrf-token" content="([^"]+)"', html2)
    csrf = (m2.group(1) if m2 else csrf)
    return opener, origin, csrf


def restart_xray(opener, origin: str, csrf: str) -> None:
    req = urllib.request.Request(
        origin + "/panel/panel/api/server/restartXrayService",
        data=b"{}",
        headers={
            "Content-Type": "application/json",
            "X-CSRF-Token": csrf,
            "X-Requested-With": "XMLHttpRequest",
        },
        method="POST",
    )
    with opener.open(req, timeout=20) as resp:
        print("xray restart", resp.read()[:120].decode(), flush=True)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--send", action="store_true")
    ap.add_argument("--no-telegram", action="store_true")
    args = ap.parse_args()
    if not args.dry_run and not args.send:
        ap.error("need --dry-run or --send")

    env = load_env(ENV_FILE)
    token = env.get("BOT_TOKEN", "")
    bot = sqlite3.connect(str(BOT_DB))
    bot.row_factory = sqlite3.Row
    xui = sqlite3.connect(str(XUI_DB))

    rows = bot.execute(
        "SELECT id, user_id, email, vless_link, subscription_url, expires_at FROM keys WHERE is_active = 1"
    ).fetchall()
    todo = []
    skip = []
    for r in rows:
        pv = parse_vless(r["vless_link"] or "")
        uid = pv.get("uuid") or ""
        if not uid:
            print("SKIP no uuid", r["user_id"])
            continue
        if vless_is_new(pv) and "ams.wingsvpn.shop" in (r["subscription_url"] or ""):
            skip.append(int(r["user_id"]))
            continue
        todo.append(r)

    print(f"active={len(rows)} already_new={len(skip)} to_fix={len(todo)}", flush=True)
    for r in todo:
        pv = parse_vless(r["vless_link"] or "")
        print(
            f"  {r['user_id']} {pv.get('host')}:{pv.get('port')} sni={pv.get('sni')} exp={r['expires_at']}",
            flush=True,
        )
    if args.dry_run:
        print("dry-run, no writes", flush=True)
        return 0

    bak = str(BOT_DB) + f".bak-reissue-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
    shutil.copy2(BOT_DB, bak)
    print("backup", bak, flush=True)

    updated = 0
    expiry_rows = 0
    for r in todo:
        pv = parse_vless(r["vless_link"] or "")
        uuid = pv["uuid"]
        safe = sanitize_email(r["email"] or "", uuid)
        new_vless = make_vless(uuid, safe, env)
        new_sub = sub_url(int(r["user_id"]))
        bot.execute(
            "UPDATE keys SET vless_link=?, subscription_url=?, email=? WHERE id=?",
            (new_vless, new_sub, safe, r["id"]),
        )
        exp = parse_dt(r["expires_at"])
        if exp:
            ts = int(exp.timestamp() * 1000)
            n = xui.execute(
                "UPDATE clients SET expiry_time=?, enable=1 WHERE uuid=?",
                (ts, uuid),
            ).rowcount
            expiry_rows += n
        updated += 1
    bot.commit()
    xui.commit()
    print(f"db updated={updated} xui_expiry_rows={expiry_rows}", flush=True)

    opener, origin, csrf = panel_login(env)
    restart_xray(opener, origin, csrf)

    if args.no_telegram:
        print("skip telegram", flush=True)
        return 0
    if not token:
        print("BOT_TOKEN empty, skip telegram", flush=True)
        return 1

    sent = failed = 0
    for r in todo:
        user_id = int(r["user_id"])
        exp = parse_dt(r["expires_at"])
        link = sub_url(user_id)
        text = (
            "🔄 <b>Обновили ссылку подписки</b>\n\n"
            "Старый адрес <code>wingsvpn.shop</code> сейчас не открывается.\n"
            f"Срок тот же: до <b>{fmt_exp(exp)}</b>\n\n"
            "🔗 <b>Новая подписка</b> (нажмите, чтобы скопировать):\n"
            f"<code>{link}</code>\n\n"
            "Что сделать:\n"
            "1. В Happ удалите старую подписку TritonVPN\n"
            "2. Нажмите «Добавить в Happ» ниже или вставьте ссылку\n"
            "3. Включите VPN — профили Турбо / Нидерланды / Hysteria"
        )
        markup = {
            "inline_keyboard": [
                [
                    {"text": "Добавить в Happ", "url": import_https(user_id, "happ")},
                    {"text": "Добавить в INCY", "url": import_https(user_id, "incy")},
                ]
            ]
        }
        code, msg = tg_send(token, user_id, text, markup)
        if code == 200:
            sent += 1
            print(f"tg ok {user_id}", flush=True)
        else:
            failed += 1
            print(f"tg FAIL {user_id} {code} {msg[:120]}", flush=True)
        time.sleep(0.08)
    print(f"telegram sent={sent} failed={failed}", flush=True)
    return 0 if failed == 0 or sent else 1


if __name__ == "__main__":
    raise SystemExit(main())
