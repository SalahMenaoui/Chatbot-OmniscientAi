import sqlite3
import json
import os
from contextlib import contextmanager
from datetime import datetime, timedelta

DEFAULT_CONFIG = {
    "botName":        "Assistant",
    "systemPrompt":   "Tu es un assistant utile et professionnel.",
    "welcomeMessage": "Bonjour ! Comment puis-je vous aider ?",
    "quickReplies":   [],
    "colorHeaderBg":  "#1a1a2e",
    "colorPrimary":   "#6c63ff",
    "proxyUrl":       "/api/chat",
}

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH  = os.path.join(BASE_DIR, "data", "omniscient.db")


def init_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    with get_conn() as conn:
        # Migrate: add config column if missing (safe on existing DB)
        cols = [r[1] for r in conn.execute("PRAGMA table_info(clients)").fetchall()]
        if "config" not in cols:
            conn.execute("ALTER TABLE clients ADD COLUMN config TEXT")
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS clients (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                name       TEXT    NOT NULL,
                client_key TEXT    UNIQUE NOT NULL,
                tier       INTEGER NOT NULL DEFAULT 1,
                config     TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS visitors (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                client_id  INTEGER NOT NULL REFERENCES clients(id),
                name       TEXT    NOT NULL,
                email      TEXT    NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS conversations (
                id               INTEGER PRIMARY KEY AUTOINCREMENT,
                visitor_id       INTEGER NOT NULL REFERENCES visitors(id),
                client_id        INTEGER NOT NULL REFERENCES clients(id),
                started_at       TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_activity_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS messages (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                conversation_id INTEGER NOT NULL REFERENCES conversations(id),
                role            TEXT    NOT NULL CHECK(role IN ('user', 'assistant')),
                content         TEXT    NOT NULL,
                timestamp       TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS dashboard_users (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                client_id     INTEGER NOT NULL REFERENCES clients(id),
                email         TEXT    UNIQUE NOT NULL,
                password_hash TEXT    NOT NULL,
                created_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS email_settings (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                client_id   INTEGER UNIQUE NOT NULL REFERENCES clients(id),
                enabled     INTEGER NOT NULL DEFAULT 0,
                delay_hours INTEGER NOT NULL DEFAULT 24,
                tone        TEXT    NOT NULL DEFAULT 'professional',
                from_name   TEXT    NOT NULL DEFAULT '',
                from_email  TEXT    NOT NULL DEFAULT ''
            );

            CREATE TABLE IF NOT EXISTS email_logs (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                visitor_id      INTEGER NOT NULL REFERENCES visitors(id),
                conversation_id INTEGER NOT NULL REFERENCES conversations(id),
                status          TEXT    NOT NULL,
                sent_at         TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                subject         TEXT,
                body_preview    TEXT
            );
        """)


@contextmanager
def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def get_client_by_key(key: str):
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM clients WHERE client_key = ?", (key,)
        ).fetchone()
        return dict(row) if row else None


def create_visitor(client_id: int, name: str, email: str):
    with get_conn() as conn:
        cur = conn.execute(
            "INSERT INTO visitors (client_id, name, email) VALUES (?, ?, ?)",
            (client_id, name, email),
        )
        visitor_id = cur.lastrowid
        cur2 = conn.execute(
            "INSERT INTO conversations (visitor_id, client_id) VALUES (?, ?)",
            (visitor_id, client_id),
        )
        conversation_id = cur2.lastrowid
    return visitor_id, conversation_id


def log_message(conversation_id: int, role: str, content: str):
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO messages (conversation_id, role, content) VALUES (?, ?, ?)",
            (conversation_id, role, content),
        )
        conn.execute(
            "UPDATE conversations SET last_activity_at = CURRENT_TIMESTAMP WHERE id = ?",
            (conversation_id,),
        )


PERIOD_DELTA = {
    "1h":  timedelta(hours=1),
    "24h": timedelta(hours=24),
    "7d":  timedelta(days=7),
    "30d": timedelta(days=30),
}

def _since(period: str):
    """Return ISO datetime string cutoff for a period key, or None."""
    delta = PERIOD_DELTA.get(period)
    if delta:
        return (datetime.utcnow() - delta).strftime("%Y-%m-%d %H:%M:%S")
    return None


def get_visitors(client_id: int, search: str = "", period: str = ""):
    q     = f"%{search}%" if search else "%"
    since = _since(period)
    date_clause = "AND v.created_at >= ?" if since else ""
    params = (client_id, q, q) + ((since,) if since else ())
    with get_conn() as conn:
        rows = conn.execute(
            f"""SELECT v.id, v.name, v.email, v.created_at,
                      COUNT(m.id)             AS message_count,
                      MAX(c.last_activity_at) AS last_seen
               FROM visitors v
               LEFT JOIN conversations c ON c.visitor_id = v.id
               LEFT JOIN messages m      ON m.conversation_id = c.id
               WHERE v.client_id = ? AND (v.name LIKE ? OR v.email LIKE ?)
               {date_clause}
               GROUP BY v.id
               ORDER BY v.created_at DESC""",
            params,
        ).fetchall()
        return [dict(r) for r in rows]


def get_stats(client_id: int, period: str = "") -> dict:
    since = _since(period)
    v_clause = "AND created_at >= ?" if since else ""
    c_clause  = "AND c.started_at >= ?" if since else ""
    p = (since,) if since else ()
    with get_conn() as conn:
        leads = conn.execute(
            f"SELECT COUNT(*) FROM visitors WHERE client_id = ? {v_clause}",
            (client_id,) + p
        ).fetchone()[0]
        convs = conn.execute(
            f"""SELECT COUNT(*) FROM conversations c
                JOIN visitors v ON v.id = c.visitor_id
                WHERE v.client_id = ? {c_clause}""",
            (client_id,) + p
        ).fetchone()[0]
        msgs = conn.execute(
            """SELECT COUNT(*) FROM messages m
               JOIN conversations c ON c.id = m.conversation_id
               JOIN visitors v ON v.id = c.visitor_id
               WHERE v.client_id = ?""",
            (client_id,)
        ).fetchone()[0]
    return {"leads": leads, "conversations": convs, "messages": msgs}


def get_daily_activity(client_id: int, days: int = 30) -> list:
    since = (datetime.utcnow() - timedelta(days=days)).strftime("%Y-%m-%d")
    with get_conn() as conn:
        rows = conn.execute(
            """SELECT date(c.started_at) AS day, COUNT(*) AS count
               FROM conversations c
               JOIN visitors v ON v.id = c.visitor_id
               WHERE v.client_id = ? AND date(c.started_at) >= ?
               GROUP BY date(c.started_at)
               ORDER BY day""",
            (client_id, since)
        ).fetchall()
    return [dict(r) for r in rows]


def get_visitor(visitor_id: int, client_id: int):
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM visitors WHERE id = ? AND client_id = ?",
            (visitor_id, client_id),
        ).fetchone()
        return dict(row) if row else None


def get_conversations(visitor_id: int):
    with get_conn() as conn:
        rows = conn.execute(
            """SELECT c.id, c.started_at, c.last_activity_at,
                      COUNT(m.id) AS message_count
               FROM conversations c
               LEFT JOIN messages m ON m.conversation_id = c.id
               WHERE c.visitor_id = ?
               GROUP BY c.id ORDER BY c.started_at DESC""",
            (visitor_id,),
        ).fetchall()
        return [dict(r) for r in rows]


def get_messages(conversation_id: int):
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM messages WHERE conversation_id = ? ORDER BY timestamp",
            (conversation_id,),
        ).fetchall()
        return [dict(r) for r in rows]


def get_email_settings(client_id: int):
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM email_settings WHERE client_id = ?", (client_id,)
        ).fetchone()
        if not row:
            conn.execute(
                "INSERT OR IGNORE INTO email_settings (client_id) VALUES (?)", (client_id,)
            )
            return {
                "client_id": client_id, "enabled": 0,
                "delay_hours": 24, "tone": "professional",
                "from_name": "", "from_email": "",
            }
        return dict(row)


def save_email_settings(client_id: int, enabled: bool, delay_hours: int,
                        tone: str, from_name: str, from_email: str):
    with get_conn() as conn:
        conn.execute(
            """INSERT INTO email_settings
                   (client_id, enabled, delay_hours, tone, from_name, from_email)
               VALUES (?, ?, ?, ?, ?, ?)
               ON CONFLICT(client_id) DO UPDATE SET
                 enabled=excluded.enabled,
                 delay_hours=excluded.delay_hours,
                 tone=excluded.tone,
                 from_name=excluded.from_name,
                 from_email=excluded.from_email""",
            (client_id, int(enabled), delay_hours, tone, from_name, from_email),
        )


def get_email_logs(client_id: int):
    with get_conn() as conn:
        rows = conn.execute(
            """SELECT el.*, v.name AS visitor_name, v.email AS visitor_email
               FROM email_logs el
               JOIN visitors v ON v.id = el.visitor_id
               WHERE v.client_id = ?
               ORDER BY el.sent_at DESC""",
            (client_id,),
        ).fetchall()
        return [dict(r) for r in rows]


DEMO_CLIENT = ("amenagement_paysager_rav", "Aménagement Paysager AV")


def seed_known_clients():
    with get_conn() as conn:
        conn.execute(
            "INSERT OR IGNORE INTO clients (client_key, name) VALUES (?, ?)",
            DEMO_CLIENT,
        )


def create_client(name: str, client_key: str):
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO clients (name, client_key) VALUES (?, ?)",
            (name, client_key),
        )


def get_dashboard_users():
    with get_conn() as conn:
        rows = conn.execute(
            """SELECT du.email, c.client_key, c.name AS client_name
               FROM dashboard_users du
               JOIN clients c ON c.id = du.client_id
               ORDER BY c.name"""
        ).fetchall()
        return [dict(r) for r in rows]


def get_all_clients():
    with get_conn() as conn:
        rows = conn.execute("SELECT * FROM clients ORDER BY name").fetchall()
        return [dict(r) for r in rows]


def get_client_config(client_key: str) -> dict:
    client = get_client_by_key(client_key)
    if not client:
        return {}
    stored = {}
    if client.get("config"):
        try:
            stored = json.loads(client["config"])
        except Exception:
            pass
    cfg = {**DEFAULT_CONFIG, **stored, "clientId": client_key}
    return cfg


def save_client_config(client_key: str, config: dict):
    with get_conn() as conn:
        conn.execute(
            "UPDATE clients SET config = ? WHERE client_key = ?",
            (json.dumps(config), client_key),
        )


def set_client_tier(client_key: str, tier: int):
    with get_conn() as conn:
        conn.execute(
            "UPDATE clients SET tier = ? WHERE client_key = ?", (tier, client_key)
        )


def rename_client(client_key: str, new_name: str):
    with get_conn() as conn:
        conn.execute(
            "UPDATE clients SET name = ? WHERE client_key = ?", (new_name.strip(), client_key)
        )


def delete_client(client_key: str):
    with get_conn() as conn:
        row = conn.execute("SELECT id FROM clients WHERE client_key = ?", (client_key,)).fetchone()
        if not row:
            return
        client_id = row["id"]
        conn.execute("DELETE FROM messages WHERE conversation_id IN (SELECT id FROM conversations WHERE visitor_id IN (SELECT id FROM visitors WHERE client_id = ?))", (client_id,))
        conn.execute("DELETE FROM conversations WHERE visitor_id IN (SELECT id FROM visitors WHERE client_id = ?)", (client_id,))
        conn.execute("DELETE FROM visitors WHERE client_id = ?", (client_id,))
        conn.execute("DELETE FROM email_settings WHERE client_id = ?", (client_id,))
        conn.execute("DELETE FROM dashboard_users WHERE client_id = ?", (client_id,))
        conn.execute("DELETE FROM clients WHERE id = ?", (client_id,))


def get_conversations_pending_email():
    with get_conn() as conn:
        rows = conn.execute(
            """SELECT c.id AS conv_id, c.visitor_id, c.last_activity_at,
                      v.name  AS visitor_name,
                      v.email AS visitor_email,
                      v.client_id,
                      cl.name AS client_name,
                      es.tone, es.delay_hours, es.from_name, es.from_email
               FROM conversations c
               JOIN visitors v        ON v.id   = c.visitor_id
               JOIN clients cl        ON cl.id  = v.client_id
               JOIN email_settings es ON es.client_id = cl.id
               WHERE es.enabled = 1
                 AND es.from_email != ''
                 AND cl.tier >= 3
                 AND datetime(c.last_activity_at, '+' || es.delay_hours || ' hours')
                     < datetime('now')
                 AND NOT EXISTS (
                   SELECT 1 FROM email_logs el WHERE el.conversation_id = c.id
                 )
                 AND (
                   SELECT COUNT(*) FROM messages m WHERE m.conversation_id = c.id
                 ) > 0"""
        ).fetchall()
        return [dict(r) for r in rows]
