# backend/services/admin_service.py
from datetime import datetime, date
from database import get_reservations_db
from repository import reservations as res_repo

async def get_audit_data():
    db = await get_reservations_db()
    cursor = await db.execute("SELECT id, capacity, state FROM tables ORDER BY id")
    tables = [dict(row) for row in await cursor.fetchall()]
    await db.close()

    now = datetime.now()
    today_str = now.strftime("%Y-%m-%d")
    current_hour = now.hour
    current_minute = now.minute
    current_total_minutes = current_hour * 60 + current_minute

    result = []
    for t in tables:
        status = "FREE"
        # Получаем все активные брони стола на сегодня с пересечением текущего часа
        db2 = await get_reservations_db()
        cur = await db2.execute(
            "SELECT * FROM bookings WHERE table_id = ? AND date = ? AND status NOT IN ('CANCELED','EXPIRED') ORDER BY start_time",
            (t["id"], today_str)
        )
        bookings = [dict(row) for row in await cur.fetchall()]
        await db2.close()

        for b in bookings:
            start_h, start_m = map(int, b["start_time"].split(":"))
            duration = b["duration"]
            end_h = start_h + duration
            if end_h >= 24:
                end_h = 24
            start_minutes = start_h * 60 + start_m
            end_minutes = end_h * 60
            # Если текущее время находится внутри временного окна брони – показываем её статус
            if start_minutes <= current_total_minutes < end_minutes:
                status = b["status"]  # HOLD, RESERVED и т.д.
                break

        result.append({
            "id": t["id"],
            "capacity": t["capacity"],
            "status": status
        })
    return result

async def get_table_history(table_id: str):
    now = datetime.now()
    today = now.date()
    current_minutes = now.hour * 60 + now.minute

    bookings = await res_repo.get_all_bookings_for_table(table_id)

    def classify(booking):
        b_date_str = booking["date"]
        try:
            b_date = datetime.strptime(b_date_str, "%Y-%m-%d").date()
        except:
            b_date = today

        start_h, start_m = map(int, booking["start_time"].split(":"))
        duration = booking["duration"]
        end_h = start_h + duration
        if end_h >= 24:
            end_h = 24
        start_minutes = start_h * 60 + start_m
        end_minutes = end_h * 60

        # Сравниваем с текущим моментом
        if b_date < today or (b_date == today and current_minutes >= end_minutes):
            return "past"
        elif b_date == today and start_minutes <= current_minutes < end_minutes:
            return "present"
        else:
            return "future"

    result = {"past": [], "present": [], "future": []}
    for b in bookings:
        items_list = await res_repo.get_order_items_for_booking(b["id"])
        items_str = ", ".join(f"{it['quantity']}x {it['item_name']}" for it in items_list) if items_list else "-"

        start_h = int(b["start_time"].split(":")[0])
        end_h = start_h + b["duration"]
        if end_h >= 24:
            end_h = 24
        time_slot = f"{b['start_time']}-{end_h:02d}:00"

        entry = {
            "id": b["id"],
            "date": b["date"],
            "time_slot": time_slot,
            "status": b["status"],
            "user_id": b["user_id"],
            "total": b["total_cost"],
            "items": items_str
        }
        category = classify(b)
        result[category].append(entry)

    return result