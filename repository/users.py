# backend/repository/users.py
from database import get_reservations_db
from domain.user import User, hash_password

async def get_user(username: str):
    db = await get_reservations_db()
    cursor = await db.execute("SELECT * FROM users WHERE username = ?", (username,))
    row = await cursor.fetchone()
    await db.close()
    return User(username=row["username"], password_hash=row["password_hash"], role=row["role"]) if row else None

async def create_user(username: str, password: str, role: str):
    db = await get_reservations_db()
    pwd_hash = hash_password(password)
    await db.execute(
        "INSERT INTO users (username, password_hash, role) VALUES (?, ?, ?)",
        (username, pwd_hash, role)
    )
    await db.commit()
    await db.close()

async def store_token(token: str, username: str):
    db = await get_reservations_db()
    await db.execute("INSERT INTO auth_tokens (token, username) VALUES (?, ?)", (token, username))
    await db.commit()
    await db.close()

async def get_username_by_token(token: str) -> str | None:
    db = await get_reservations_db()
    cursor = await db.execute("SELECT username FROM auth_tokens WHERE token = ?", (token,))
    row = await cursor.fetchone()
    await db.close()
    return row["username"] if row else None