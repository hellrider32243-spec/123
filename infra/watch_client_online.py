#!/usr/bin/env python3
"""Пишет админу в Telegram, когда выбранный VPN-клиент появляется онлайн на 4VPS.

Смотрит lastOnline в x-ui, не Telegram last-seen.
"""
from __future__ import annotations

import json
import os
import sqlite3
import sys
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, "/opt/nordwings/app")
os.chdir("/opt/nordwings/app")

from dotenv import load_dotenv

load_dotenv("/opt/nordwings/app/.env")

from sync_nl_4vps_clients import NlPanel, uuid_from_vless  # noqa: E402

BOT_DB = os.getenv("DB_PATH", "/opt/3xui-bot/bot.db")
STATE_PATH = Path(os.getenv("WATCH_ONLINE_STATE", "/var/lib/nordwings/watch_online_state.json"))
WATCH_USERNAMES = [
    x.strip().lstrip("@").lower()
    for x in os.getenv("WATCH_USERNAMES", "oxedit").split(",")
    if x.strip()
]
ADMIN_ID = int(os.getenv("WATCH_ADMIN_ID") or os.getenv("ADMIN_ID") or "858565509")
ONLINE_WINDOW_SEC = int(os.getenv("WATCH_ONLINE_SEC", "180"))
BOT_TOKEN = os.getenv("BOT_TOKEN") or os.getenv("TG_BOT_TOKEN") or ""
MSK = timezone(timedelta(hours=3))


def msk_fmt(ms: int) -> str:
    if not ms:
        return "—"
    dt = datetime.fromtimestamp(ms / 1000, tz=timezone.utc).astimezone(MSK)
    return dt.strftime("%d.%m.%Y %H:%M:%S") + " МСК"


def mb(n: int) -> str:
    return f"{(n or 0) / 1024 / 1024:.1f} МБ"


def load_state() -> dict:
    if not STATE_PATH.exists():
        return {}
    try:
        return json.loads(STATE_PATH.read_text())
    except Exception:
        return {}


def save_state(state: dict) -> None:
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    tmp = STATE_PATH.with_suffix(".tmp")
    tmp.write_text(json.dumps(state, ensure_ascii=False, indent=2))
    tmp.replace(STATE_PATH)


def tg_send(text: str) -> None:
    if not BOT_TOKEN or not ADMIN_ID:
        print("skip telegram: no token/admin", flush=True)
        return
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    body = urllib.parse.urlencode(
        {"chat_id": ADMIN_ID, "text": text, "parse_mode": "HTML"}
    ).encode()
    req = urllib.request.Request(url, data=body, method="POST")
    with urllib.request.urlopen(req, timeout=20) as resp:
        raw = json.loads(resp.read().decode())
        if not raw.get("ok"):
            raise RuntimeError(f"telegram send failed: {raw}")


def watched_users() -> list[dict]:
    con = sqlite3.connect(BOT_DB)
    con.row_factory = sqlite3.Row
    out = []
    for uname in WATCH_USERNAMES:
        u = con.execute(
            "SELECT user_id, username, first_name FROM users WHERE lower(IFNULL(username,'')) = ?",
            (uname,),
        ).fetchone()
        if not u:
            print(f"user @{uname} not in bot.db", flush=True)
            continue
        key = con.execute(
            "SELECT vless_link, email, expires_at FROM keys WHERE user_id=? AND is_active=1 ORDER BY id DESC LIMIT 1",
            (u["user_id"],),
        ).fetchone()
        uid = uuid_from_vless(key["vless_link"] if key else "")
        if not uid:
            print(f"@{uname} has no active vless uuid", flush=True)
            continue
        out.append(
            {
                "username": u["username"] or uname,
                "first_name": u["first_name"] or "",
                "user_id": int(u["user_id"]),
                "uuid": uid,
                "expires_at": key["expires_at"] if key else "",
            }
        )
    con.close()
    return out


def panel_stats_by_uuid(panel: NlPanel) -> dict[str, dict]:
    code, listed = panel.call("GET", "/inbounds/list")
    if code != 200 or not (listed or {}).get("success"):
        raise RuntimeError(f"inbounds/list failed {code} {listed}")
    by_uuid: dict[str, dict] = {}
    for ib in listed.get("obj") or []:
        remark = ib.get("remark") or f"inbound {ib.get('id')}"
        for st in ib.get("clientStats") or []:
            uuid = (st.get("uuid") or "").strip()
            if not uuid:
                continue
            last = int(st.get("lastOnline") or 0)
            prev = by_uuid.get(uuid)
            if not prev or last >= int(prev.get("lastOnline") or 0):
                by_uuid[uuid] = {
                    "lastOnline": last,
                    "up": int(st.get("up") or 0),
                    "down": int(st.get("down") or 0),
                    "email": st.get("email") or "",
                    "inbound": remark,
                }
    return by_uuid


def main() -> int:
    users = watched_users()
    if not users:
        print("no watched users", flush=True)
        return 0
    panel = NlPanel()
    panel.login()
    stats = panel_stats_by_uuid(panel)
    now_ms = int(datetime.now(timezone.utc).timestamp() * 1000)
    state = load_state()
    users_state = state.setdefault("users", {})

    for u in users:
        key = str(u["user_id"])
        st = stats.get(u["uuid"]) or {}
        last_ms = int(st.get("lastOnline") or 0)
        online = bool(last_ms and (now_ms - last_ms) <= ONLINE_WINDOW_SEC * 1000)
        prev = users_state.get(key) or {}
        was_online = bool(prev.get("was_online"))
        handle = f"@{u['username']}"
        name = u["first_name"]
        who = f"{handle}" + (f" ({name})" if name else "")

        print(
            f"{handle} online={online} last={msk_fmt(last_ms)} "
            f"up={mb(st.get('up', 0))} down={mb(st.get('down', 0))} via={st.get('inbound') or '—'}",
            flush=True,
        )

        if online and not was_online:
            tg_send(
                "🟢 <b>Онлайн в VPN</b>\n"
                f"{who}\n"
                f"⏰ {msk_fmt(last_ms)}\n"
                f"📡 {st.get('inbound') or '—'}\n"
                f"📊 ↑ {mb(st.get('up', 0))}  ↓ {mb(st.get('down', 0))}"
            )
            print(f"notified online {handle}", flush=True)
        elif (not online) and was_online:
            tg_send(
                "⚪️ <b>Оффлайн</b>\n"
                f"{who}\n"
                f"последний раз: {msk_fmt(last_ms)}\n"
                f"📊 ↑ {mb(st.get('up', 0))}  ↓ {mb(st.get('down', 0))}"
            )
            print(f"notified offline {handle}", flush=True)

        users_state[key] = {
            "username": u["username"],
            "was_online": online,
            "last_online_ms": last_ms,
            "up": int(st.get("up") or 0),
            "down": int(st.get("down") or 0),
            "inbound": st.get("inbound") or "",
            "checked_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        }

    state["checked_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    save_state(state)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
