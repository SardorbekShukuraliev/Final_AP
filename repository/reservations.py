# backend/repository/reservations.py
from database import get_reservations_db

async def create_reservation(reservation: dict) -> int:
    db = await get_reservations_db()
    cursor = await db.execute(
        "INSERT INTO bookings (table_id, user_id, date, start_time, duration, status, total_cost, food_order_id) VALUES (?,?,?,?,?,?,?,?)",
        (reservation["table_id"], reservation["user_id"], reservation["date"],
         reservation["start_time"], reservation["duration"], reservation["status"],
         reservation["total_cost"], reservation["food_order_id"])
    )
    await db.commit()
    res_id = cursor.lastrowid          # ← исправлено
    await db.close()
    return res_id

async def get_conflicting_reservations(table_id: str, date: str, start_time: str, end_time: str) -> list:
    """Возвращает список активных броней (не CANCELED, не EXPIRED), пересекающихся с запрашиваемым интервалом."""
    db = await get_reservations_db()
    req_start_h = int(start_time.split(":")[0])
    req_end_h = int(end_time.split(":")[0])
    if end_time == "00:00":
        req_end_h = 24

    cursor = await db.execute("""
        SELECT * FROM bookings
        WHERE table_id = ? AND date = ? AND status NOT IN ('CANCELED','EXPIRED')
          AND ? < (CAST(SUBSTR(start_time,1,2) AS INTEGER) + duration)
          AND ? > CAST(SUBSTR(start_time,1,2) AS INTEGER)
    """, (table_id, date, req_start_h, req_end_h))
    rows = await cursor.fetchall()
    await db.close()
    return [dict(row) for row in rows]

async def get_active_hold(table_id: str) -> dict | None:
    db = await get_reservations_db()
    cursor = await db.execute(
        "SELECT * FROM bookings WHERE table_id = ? AND status = 'HOLD' ORDER BY id DESC LIMIT 1",
        (table_id,)
    )
    row = await cursor.fetchone()
    await db.close()
    return dict(row) if row else None

async def update_reservation_status(booking_id: int, new_status: str):
    db = await get_reservations_db()
    await db.execute("UPDATE bookings SET status = ? WHERE id = ?", (new_status, booking_id))
    await db.commit()
    await db.close()

async def get_booking_by_id(booking_id: int):
    db = await get_reservations_db()
    cursor = await db.execute("SELECT * FROM bookings WHERE id = ?", (booking_id,))
    row = await cursor.fetchone()
    await db.close()
    return dict(row) if row else None

async def get_all_bookings_for_table(table_id: str):
    db = await get_reservations_db()
    cursor = await db.execute(
        "SELECT * FROM bookings WHERE table_id = ? AND status NOT IN ('CANCELED','EXPIRED') ORDER BY date, start_time",
        (table_id,)
    )
    rows = await cursor.fetchall()
    await db.close()
    return [dict(row) for row in rows]

async def get_order_items_for_booking(booking_id: int) -> list:
    db = await get_reservations_db()
    cursor = await db.execute(
        "SELECT item_name, quantity FROM order_items WHERE booking_id = ?",
        (booking_id,)
    )
    rows = await cursor.fetchall()
    await db.close()
    return [dict(row) for row in rows]

async def get_user_reservations(user_id: str) -> list:
    """Возвращает все активные брони пользователя (не CANCELED, не EXPIRED)."""
    db = await get_reservations_db()
    cursor = await db.execute(
        "SELECT * FROM bookings WHERE user_id = ? AND status NOT IN ('CANCELED','EXPIRED') ORDER BY date DESC, start_time ASC",
        (user_id,)
    )
    rows = await cursor.fetchall()
    await db.close()
    return [dict(row) for row in rows]

async def get_busy_table_ids(date: str, start_time: str, end_time: str) -> list:
    """
    Возвращает ID столов, имеющих активные брони (не CANCELED, не EXPIRED)
    на заданную дату, пересекающиеся с интервалом [start_time, end_time).
    """
    db = await get_reservations_db()
    req_start_h = int(start_time.split(":")[0])
    req_end_h = int(end_time.split(":")[0])
    if end_time == "00:00":
        req_end_h = 24

    cursor = await db.execute("""
        SELECT DISTINCT table_id FROM bookings
        WHERE date = ? 
          AND status NOT IN ('CANCELED','EXPIRED')
          AND (
              ? < (CAST(SUBSTR(start_time,1,2) AS INTEGER) + duration)
              AND ? > CAST(SUBSTR(start_time,1,2) AS INTEGER)
          )
    """, (date, req_start_h, req_end_h))
    rows = await cursor.fetchall()
    await db.close()
    return [row["table_id"] for row in rows]

async def cancel_all_holds_for_table(table_id: str):
    db = await get_reservations_db()
    await db.execute("UPDATE bookings SET status = 'EXPIRED' WHERE table_id = ? AND status = 'HOLD'", (table_id,))
    await db.commit()
    await db.close()