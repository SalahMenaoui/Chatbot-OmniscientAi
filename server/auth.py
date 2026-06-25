import bcrypt
from server import models


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def check_password(password: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode(), hashed.encode())
    except Exception:
        return False


def authenticate_dashboard_user(email: str, password: str):
    with models.get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM dashboard_users WHERE email = ?", (email,)
        ).fetchone()
    if not row:
        return None
    user = dict(row)
    if check_password(password, user["password_hash"]):
        return user
    return None


def create_dashboard_user(client_key: str, email: str, password: str):
    client = models.get_client_by_key(client_key)
    if not client:
        raise ValueError(f"Client '{client_key}' not found.")
    with models.get_conn() as conn:
        conn.execute(
            "INSERT INTO dashboard_users (client_id, email, password_hash, password_plain) VALUES (?, ?, ?, ?)",
            (client["id"], email, hash_password(password), password),
        )
