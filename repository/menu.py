# backend/repository/menu.py
from database import get_reservations_db      # <-- исправлено

async def get_all_menu():
    db = await get_reservations_db()
    cursor = await db.execute("SELECT id, name, price, category FROM menu_items")
    rows = await cursor.fetchall()
    await db.close()
    return [dict(row) for row in rows]

async def get_menu_item(menu_id: str):
    db = await get_reservations_db()
    cursor = await db.execute("SELECT id, name, price, category FROM menu_items WHERE id = ?", (menu_id,))
    row = await cursor.fetchone()
    await db.close()
    return dict(row) if row else None