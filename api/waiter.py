# backend/api/waiter.py
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends, HTTPException, Query
from auth import require_role
from pydantic import BaseModel
import json
from datetime import datetime
import uuid
from database import get_reservations_db
from services.websocket_manager import waiter_manager

router = APIRouter()
router_http = APIRouter(dependencies=[Depends(require_role("waiter"))])

# --- WebSocket менеджер официантов (уже должен быть импортирован из services) ---
from services.websocket_manager import waiter_manager

@router_http.get("/tables")
async def get_all_tables():
    from services.admin_service import get_audit_data
    tables = await get_audit_data()
    return tables

@router_http.get("/tables/{table_id}/active-session")
async def get_active_session(table_id: str):
    from database import get_reservations_db
    now = datetime.now()
    today = now.strftime("%Y-%m-%d")
    current_time = now.strftime("%H:%M")
    db = await get_reservations_db()
    cursor = await db.execute("""
        SELECT * FROM bookings
        WHERE table_id = ? AND date = ? AND status IN ('RESERVED','OCCUPIED','HOLD')
          AND start_time <= ? AND (CAST(SUBSTR(start_time,1,2) AS INTEGER) + duration) > ?
        ORDER BY id DESC LIMIT 1
    """, (table_id, today, current_time, int(current_time.split(':')[0])))
    booking = await cursor.fetchone()
    await db.close()
    if booking:
        return {
            "booking_id": booking["id"],
            "customer_name": booking["user_id"],
            "time_slot": f"{booking['start_time']} + {booking['duration']}h"
        }
    raise HTTPException(404, "No active session")

@router_http.post("/orders")
async def create_order(body: dict):
    from database import get_reservations_db

    table_id = body["table_id"]
    items = body.get("items", [])
    booking_id = body.get("booking_id")

    db = await get_reservations_db()
    if not booking_id:
        now = datetime.now()
        today = now.strftime("%Y-%m-%d")
        cursor = await db.execute(
            "SELECT id FROM bookings WHERE table_id = ? AND date = ? AND status IN ('RESERVED','OCCUPIED','HOLD') LIMIT 1",
            (table_id, today)
        )
        row = await cursor.fetchone()
        if row:
            booking_id = row["id"]
        else:
            booking_id = str(uuid.uuid4())
            await db.execute(
                "INSERT INTO bookings (id, table_id, user_id, date, start_time, duration, status, total_cost) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (booking_id, table_id, "walk-in", today, now.strftime("%H:%M"), 1, "OCCUPIED", 0)
            )
            await db.execute("UPDATE tables SET state = 'OCCUPIED' WHERE id = ?", (table_id,))
            await db.commit()

    order_id = str(uuid.uuid4())
    total = sum(item.get("price", 0) * item.get("qty", 0) for item in items)
    await db.execute(
        "INSERT INTO food_orders (id, booking_id, status, items_json, total_food_cost) VALUES (?, ?, ?, ?, ?)",
        (order_id, booking_id, "PENDING", json.dumps(items), total)
    )
    for item in items:
        name = item.get("name", "Блюдо")
        qty = item.get("qty", 1)
        await db.execute(
            "INSERT INTO order_items (booking_id, item_name, quantity) VALUES (?, ?, ?)",
            (booking_id, name, qty)
        )
    await db.commit()
    await db.close()

    return {
        "id": order_id,
        "table_id": table_id,
        "booking_id": booking_id,
        "items": items,
        "total_cost": total,
        "status": "PENDING"
    }

@router_http.post("/orders/{order_id}/pay_cash")
async def pay_cash(order_id: str):
    db = await get_reservations_db()
    cursor = await db.execute("SELECT id FROM food_orders WHERE id = ?", (order_id,))
    if not await cursor.fetchone():
        await db.close()
        raise HTTPException(404, "Order not found")
    await db.execute("UPDATE food_orders SET status = 'PAID_CASH' WHERE id = ?", (order_id,))
    await db.commit()
    await db.close()
    return {"message": "Оплата наличными принята"}

@router_http.post("/orders/{order_id}/pay_card")
async def pay_card(order_id: str):
    db = await get_reservations_db()
    cursor = await db.execute("SELECT id FROM food_orders WHERE id = ?", (order_id,))
    if not await cursor.fetchone():
        await db.close()
        raise HTTPException(404, "Order not found")
    await db.execute("UPDATE food_orders SET status = 'PAID_CARD' WHERE id = ?", (order_id,))
    await db.commit()
    await db.close()
    return {"message": "Оплата картой принята"}

@router_http.post("/orders/{order_id}/close_table")
async def close_table(order_id: str):
    db = await get_reservations_db()
    cursor = await db.execute("SELECT booking_id FROM food_orders WHERE id = ?", (order_id,))
    row = await cursor.fetchone()
    if not row:
        await db.close()
        raise HTTPException(404, "Order not found")
    booking_id = row["booking_id"]
    # Получить table_id из bookings
    cursor = await db.execute("SELECT table_id FROM bookings WHERE id = ?", (booking_id,))
    booking_row = await cursor.fetchone()
    if not booking_row:
        await db.close()
        raise HTTPException(404, "Booking not found")
    table_id = booking_row["table_id"]
    # Завершаем бронь и освобождаем стол
    await db.execute("UPDATE bookings SET status = 'CLEARED' WHERE id = ?", (booking_id,))
    await db.execute("UPDATE tables SET state = 'FREE' WHERE id = ?", (table_id,))
    # Удалять заказ не будем, оставляем в истории
    await db.commit()
    await db.close()
    return {"message": f"Стол {table_id} освобождён"}

@router_http.get("/menu")
async def get_menu():
    from services.menu_service import get_available_menu
    return await get_available_menu()

# WebSocket
@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket, token: str = Query(...)):
    from repository import users as user_repo
    username = await user_repo.get_username_by_token(token)
    if not username:
        await websocket.close(code=4001, reason="Invalid token")
        return
    user = await user_repo.get_user(username)
    if not user or user.role != "waiter":
        await websocket.close(code=4003, reason="Forbidden")
        return

    await waiter_manager.connect(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        waiter_manager.disconnect(websocket)
    except Exception:
        waiter_manager.disconnect(websocket)