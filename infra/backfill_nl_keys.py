#!/usr/bin/env python3
"""Backfill bot.db keys from 4VPS x-ui so Happ JSON works without Frankfurt.

- Inserts missing active keys for `{telegram_id}_*` x-ui clients (NL vless + AMS sub URL).
- Telegram only users seen online recently (default 14 days).

  python3 infra/backfill_nl_keys.py --dry-run
  python3 infra/backfill_nl_keys.py --apply
  python3 infra/backfill_nl_keys.py --apply --send
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import sqlite3
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))
from xui_vless_lookup import make_nl_tcp_vless  # noqa: E402

ENV_FILE = Path(os.getenv("NORDWINGS_ENV", "/opt/nordwings/app/.env"))
BOT_DB = Path(os.getenv("DB_PATH", "/opt/3xui-bot/bot.db"))
XUI_DB = Path(os.getenv("XUI_DB_PATH", "/etc/x-ui/x-ui.db"))
SUB_BASE = os.getenv("SUBSCRIPTION_BASE_URL", "https://ams.wingsvpn.shop/miniapp/sub").rstrip("/")
PROFILE = "TritonVPN"
_TG_EMAIL = re.compile(r"^(\d{5,15})_")


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


def sub_url(user_id: int) -> str:
    return f"{SUB_BASE}/{user_id}#{PROFILE}"


def import_https(user_id: int, app: str) -> str:
    return f"{SUB_BASE}/{user_id}?action=add&app={app}#{PROFILE}"


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
            data = json.loads(resp.read().decode())
            if data.get("ok"):
                return 200, "ok"
            return 400, str(data)[:200]
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()[:300]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--send", action="store_true", help="Telegram recently-online users")
    ap.add_argument("--online-days", type=int, default=14)
    args = ap.parse_args()
    if not args.dry_run and not args.apply:
        ap.error("need --dry-run or --apply")

    env = load_env(ENV_FILE)
    token = env.get("BOT_TOKEN", "")
    bot = sqlite3.connect(str(BOT_DB))
    bot.row_factory = sqlite3.Row
    xui = sqlite3.connect(str(XUI_DB))
    xui.row_factory = sqlite3.Row
    now_ms = int(datetime.now(timezone.utc).timestamp() * 1000)
    online_cut = now_ms - args.online_days * 86400 * 1000

    last_online = {
        r["email"]: int(r["last_online"] or 0)
        for r in xui.execute("SELECT email, last_online FROM client_traffics")
    }
    active = {int(r["user_id"]) for r in bot.execute("SELECT user_id FROM keys WHERE is_active = 1")}

    by_tg: dict[int, sqlite3.Row] = {}
    for r in xui.execute("SELECT id, email, uuid, enable, expiry_time FROM clients WHERE enable = 1"):
        m = _TG_EMAIL.match(r["email"] or "")
        if not m:
            continue
        tid = int(m.group(1))
        prev = by_tg.get(tid)
        if prev is None or last_online.get(r["email"], 0) >= last_online.get(prev["email"], 0):
            by_tg[tid] = r

    to_insert = []
    notify = []
    for tid, r in sorted(by_tg.items()):
        if tid in active:
            continue
        lo = last_online.get(r["email"], 0)
        to_insert.append((tid, r, lo))
        if lo >= online_cut:
            notify.append((tid, r, lo))

    print(
        f"xui_tg_clients={len(by_tg)} missing_keys={len(to_insert)} notify_online_{args.online_days}d={len(notify)}",
        flush=True,
    )
    for tid, r, lo in notify:
        age_h = round((now_ms - lo) / 3600000, 1) if lo else "never"
        print(f"  notify {tid} {r['email']} last_h={age_h}", flush=True)
    if args.dry_run:
        print("dry-run, no writes", flush=True)
        return 0

    bak = str(BOT_DB) + f".bak-backfill-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
    shutil.copy2(BOT_DB, bak)
    print("backup", bak, flush=True)

    inserted = 0
    default_exp = (datetime.now() + timedelta(days=365)).isoformat()
    for tid, r, lo in to_insert:
        uuid = str(r["uuid"])
        email = str(r["email"])
        vless = make_nl_tcp_vless(uuid, email)
        exp_ms = int(r["expiry_time"] or 0)
        if exp_ms:
            exp = datetime.fromtimestamp(exp_ms / 1000).isoformat()
        else:
            exp = default_exp
        bot.execute("UPDATE keys SET is_active = 0 WHERE user_id = ? AND is_active = 1", (tid,))
        bot.execute(
            "INSERT INTO keys (user_id, email, vless_link, subscription_url, expires_at, is_active) "
            "VALUES (?, ?, ?, ?, ?, 1)",
            (tid, email, vless, sub_url(tid), exp),
        )
        inserted += 1
    bot.commit()
    print(f"inserted_keys={inserted}", flush=True)

    if not args.send:
        print("skip telegram", flush=True)
        return 0
    if not token:
        print("BOT_TOKEN empty", flush=True)
        return 1

    sent = failed = 0
    for tid, r, lo in notify:
        link = sub_url(tid)
        text = (
            "🔄 <b>Обновите подписку TritonVPN</b>\n\n"
            "Сервер во Франкфурте больше не используется.\n"
            "Профили: Турбо :443 · Нидерланды :49714 · Hysteria :41028\n\n"
            "🔗 <b>Новая ссылка</b> (нажмите, чтобы скопировать):\n"
            f"<code>{link}</code>\n\n"
            "В Happ удалите старую подписку TritonVPN и нажмите «Добавить в Happ»."
        )
        markup = {
            "inline_keyboard": [
                [
                    {"text": "Добавить в Happ", "url": import_https(tid, "happ")},
                    {"text": "Добавить в INCY", "url": import_https(tid, "incy")},
                ]
            ]
        }
        code, msg = tg_send(token, tid, text, markup)
        if code == 200:
            sent += 1
            print(f"tg ok {tid}", flush=True)
        else:
            failed += 1
            print(f"tg FAIL {tid} {code} {msg[:120]}", flush=True)
        time.sleep(0.08)
    print(f"telegram sent={sent} failed={failed}", flush=True)
    return 0 if failed == 0 or sent else 1


if __name__ == "__main__":
    raise SystemExit(main())
