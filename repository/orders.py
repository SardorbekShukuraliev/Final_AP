# backend/repository/orders.py
import json
from database import get_reservations_db

async def create_food_order(order: dict):
    db = await get_reservations_db()
    await db.execute(
        "INSERT INTO food_orders (id, booking_id, status, items_json, total_food_cost) VALUES (?,?,?,?,?)",
        (order["id"], order["booking_id"], order["status"],
         json.dumps(order["items"]), order["total_food_cost"])
    )
    await db.commit()
    await db.close()

async def get_food_order(order_id: str):
    db = await get_reservations_db()
    cursor = await db.execute("SELECT * FROM food_orders WHERE id = ?", (order_id,))
    row = await cursor.fetchone()
    await db.close()
    if not row:
        return None
    data = dict(row)
    data["items"] = json.loads(data["items_json"])
    return data

async def get_order_items(booking_id: int):
    db = await get_reservations_db()
    cursor = await db.execute(
        "SELECT oi.menu_id, oi.quantity, oi.item_name FROM order_items WHERE booking_id = ?",
        (booking_id,)
    )
    rows = await cursor.fetchall()
    await db.close()
    return [dict(row) for row in rows]