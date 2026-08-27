#!/usr/bin/env python3
"""Patch live 4VPS subscription handlers to NL x-ui fallback (run on the VPS)."""
from __future__ import annotations

import shutil
from datetime import datetime
from pathlib import Path

WEB = Path("/opt/nordwings-web/backend.py")
BOT = Path("/opt/nordwings/app/bot_api.py")
STAMP = datetime.now().strftime("%Y%m%d-%H%M%S")

WEB_OLD = '''def get_stable_vless_body(user_id: int) -> Optional[str]:
    """
    Стабильный vless из bot.db.
    Не использовать x-ui :2096/sub — там sid/spx меняются при каждом запросе.
    """
    conn = get_db_connection()
    try:
        if not table_exists(conn, "keys"):
            return None
        columns = get_table_columns(conn, "keys")
        where_clause = "WHERE user_id = ?"
        if "is_active" in columns:
            where_clause += " AND is_active = 1"
        order_clause = "ORDER BY id DESC" if "id" in columns else ""
        if "vless_link" not in columns:
            return None
        row = conn.execute(
            f"SELECT vless_link FROM keys {where_clause} {order_clause} LIMIT 1",
            (user_id,),
        ).fetchone()
        if row and row["vless_link"]:
            link = str(row["vless_link"]).strip()
            if link.startswith("vless://"):
                return link
        return None
    finally:
        conn.close()
'''

WEB_NEW = '''def get_stable_vless_body(user_id: int) -> Optional[str]:
    """
    Стабильный vless из bot.db, иначе UUID с 4VPS x-ui ({telegram_id}_*).
    Не использовать x-ui :2096/sub и не ходить на Франкфурт.
    """
    conn = get_db_connection()
    try:
        if table_exists(conn, "keys"):
            columns = get_table_columns(conn, "keys")
            where_clause = "WHERE user_id = ?"
            if "is_active" in columns:
                where_clause += " AND is_active = 1"
            order_clause = "ORDER BY id DESC" if "id" in columns else ""
            if "vless_link" in columns:
                row = conn.execute(
                    f"SELECT vless_link FROM keys {where_clause} {order_clause} LIMIT 1",
                    (user_id,),
                ).fetchone()
                if row and row["vless_link"]:
                    link = str(row["vless_link"]).strip()
                    if link.startswith("vless://"):
                        return link
    finally:
        conn.close()
    try:
        from xui_vless_lookup import lookup_nl_client
        hit = lookup_nl_client(int(user_id))
        if hit and hit.get("vless"):
            return str(hit["vless"])
    except Exception:
        pass
    return None
'''

BOT_OLD = '''    key = get_active_key(user_id)
    if not key:
        raise web.HTTPNotFound(text="Subscription not found")
'''

BOT_NEW = '''    key = get_active_key(user_id)
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
'''


def patch(path: Path, old: str, new: str, label: str) -> None:
    text = path.read_text()
    if new.strip() in text:
        print(label, "already patched")
        return
    if old not in text:
        raise SystemExit(f"{label}: old block not found in {path}")
    shutil.copy2(path, str(path) + f".bak-{STAMP}")
    path.write_text(text.replace(old, new, 1))
    print(label, "ok", path)


def main() -> None:
    patch(WEB, WEB_OLD, WEB_NEW, "web")
    patch(BOT, BOT_OLD, BOT_NEW, "bot")
    for src, dst in (
        ("www.apple.com", "deepl.com"),
        ('or "log"', 'or "ws"'),
    ):
        pass
    bot = BOT.read_text()
    bot2 = bot.replace('or "www.apple.com"', 'or "deepl.com"').replace(
        'CFG.sni or "www.apple.com"', 'CFG.sni or "deepl.com"'
    ).replace('CFG.grpc_service_name or "log"', 'CFG.grpc_service_name or "ws"')
    bot2 = bot2.replace('os.getenv("SNI", "wingsvpn.shop")', 'os.getenv("SNI", "deepl.com")')
    bot2 = bot2.replace(
        'os.getenv("PUBLIC_VLESS_HOST", "wingsvpn.shop")',
        'os.getenv("PUBLIC_VLESS_HOST", "139.28.240.160")',
    )
    bot2 = bot2.replace(
        'os.getenv("PUBLIC_BASE_URL", "https://wingsvpn.shop")',
        'os.getenv("PUBLIC_BASE_URL", "https://ams.wingsvpn.shop")',
    )
    bot2 = bot2.replace(
        'os.getenv("MINI_APP_URL", "https://wingsvpn.shop/miniapp/")',
        'os.getenv("MINI_APP_URL", "https://ams.wingsvpn.shop/miniapp/")',
    )
    bot2 = bot2.replace(
        'os.getenv("SUBSCRIPTION_BASE_URL", "https://wingsvpn.shop/s")',
        'os.getenv("SUBSCRIPTION_BASE_URL", "https://ams.wingsvpn.shop/miniapp/sub")',
    )
    if bot2 != bot:
        if ".bak-" not in str(list(BOT.parent.glob("bot_api.py.bak-*"))[-1:]):
            shutil.copy2(BOT, str(BOT) + f".bak-fra-{STAMP}")
        BOT.write_text(bot2)
        print("bot fra defaults rewritten")
    print("done")


if __name__ == "__main__":
    main()
