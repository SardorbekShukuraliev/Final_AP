# backend/api/chef.py
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends, HTTPException, Query
from auth import require_role
from database import get_reservations_db
import json
from collections import deque

router = APIRouter()
router_http = APIRouter(dependencies=[Depends(require_role("chef"))])

# История команд для Undo/Redo (общий стек для всех заказов)
undo_stack = deque()
redo_stack = deque()

@router_http.get("/orders")
async def get_kitchen_orders():
    db = await get_reservations_db()
    cursor = await db.execute("""
        SELECT fo.id, fo.booking_id, fo.status, b.table_id
        FROM food_orders fo
        JOIN bookings b ON fo.booking_id = b.id
        WHERE fo.status IN ('PENDING', 'PREPARING')
        ORDER BY fo.id
    """)
    orders = []
    async for row in cursor:
        # Получаем позиции из order_items
        items_cursor = await db.execute(
            "SELECT item_name, quantity FROM order_items WHERE booking_id = ?",
            (row["booking_id"],)
        )
        items = []
        async for item in items_cursor:
            items.append({
                "name": item["item_name"],
                "qty": item["quantity"]
            })
        orders.append({
            "id": row["id"],
            "table_id": row["table_id"],
            "status": row["status"],
            "items": items
        })
    await db.close()
    return orders

@router_http.post("/orders/{order_id}/accept")
async def accept_order(order_id: str):
    """Переводит заказ в статус PREPARING."""
    db = await get_reservations_db()
    cursor = await db.execute("SELECT * FROM food_orders WHERE id = ? AND status = 'PENDING'", (order_id,))
    order = await cursor.fetchone()
    if not order:
        raise HTTPException(404, "Order not found or not PENDING")
    # Сохраняем в историю для undo
    undo_stack.append(("accept", order_id))
    redo_stack.clear()
    await db.execute("UPDATE food_orders SET status = 'PREPARING' WHERE id = ?", (order_id,))
    await db.commit()
    await db.close()
    return {"status": "PREPARING"}

@router_http.post("/orders/{order_id}/ready")
async def mark_ready(order_id: str):
    """Переводит заказ в READY и оповещает официантов через WebSocket."""
    db = await get_reservations_db()
    cursor = await db.execute(
        "SELECT fo.id, fo.booking_id, b.table_id FROM food_orders fo JOIN bookings b ON fo.booking_id = b.id WHERE fo.id = ? AND fo.status = 'PREPARING'",
        (order_id,)
    )
    order = await cursor.fetchone()
    if not order:
        raise HTTPException(404, "Order not found or not PREPARING")
    # Получаем названия блюд
    items_cursor = await db.execute(
        "SELECT item_name, quantity FROM order_items WHERE booking_id = ?",
        (order["booking_id"],)
    )
    items_list = [f"{qty}x {name}" async for name, qty in items_cursor]
    # Меняем статус
    undo_stack.append(("ready", order_id))
    redo_stack.clear()
    await db.execute("UPDATE food_orders SET status = 'READY' WHERE id = ?", (order_id,))
    await db.commit()
    await db.close()
    # Отправка WebSocket официантам
    from services.websocket_manager import waiter_manager
    message = json.dumps({
        "event": "order_ready",
        "table_id": order["table_id"],
        "items": items_list
    })
    await waiter_manager.broadcast(message)
    return {"status": "READY"}

@router_http.post("/undo")
async def undo_action():
    if not undo_stack:
        raise HTTPException(400, "Nothing to undo")
    action, order_id = undo_stack.pop()
    db = await get_reservations_db()
    if action == "accept":
        await db.execute("UPDATE food_orders SET status = 'PENDING' WHERE id = ?", (order_id,))
    elif action == "ready":
        await db.execute("UPDATE food_orders SET status = 'PREPARING' WHERE id = ?", (order_id,))
    await db.commit()
    await db.close()
    redo_stack.append((action, order_id))
    return {"status": "undone"}

@router_http.post("/redo")
async def redo_action():
    if not redo_stack:
        raise HTTPException(400, "Nothing to redo")
    action, order_id = redo_stack.pop()
    db = await get_reservations_db()
    if action == "accept":
        await db.execute("UPDATE food_orders SET status = 'PREPARING' WHERE id = ?", (order_id,))
    elif action == "ready":
        await db.execute("UPDATE food_orders SET status = 'READY' WHERE id = ?", (order_id,))
        # При redo "ready" тоже нужно уведомить официантов
        cursor = await db.execute(
            "SELECT b.table_id FROM food_orders fo JOIN bookings b ON fo.booking_id = b.id WHERE fo.id = ?",
            (order_id,)
        )
        row = await cursor.fetchone()
        if row:
            from services.websocket_manager import waiter_manager
            message = json.dumps({
                "event": "order_ready",
                "table_id": row["table_id"],
                "items": []  # можно не дублировать список
            })
            await waiter_manager.broadcast(message)
    await db.commit()
    await db.close()
    undo_stack.append((action, order_id))
    return {"status": "redone"}

# WebSocket для кухни (оповещения о новых заказах)
@router.websocket("/ws")
async def chef_websocket(websocket: WebSocket, token: str = Query(...)):
    # Проверка токена кухни
    from repository import users as user_repo
    username = await user_repo.get_username_by_token(token)
    if not username:
        await websocket.close(code=4001)
        return
    user = await user_repo.get_user(username)
    if not user or user.role != "chef":
        await websocket.close(code=4003)
        return
    await websocket.accept()
    try:
        while True:
            await websocket.receive_text()  # поддерживаем соединение
    except WebSocketDisconnect:
        pass