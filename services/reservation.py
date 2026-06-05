# backend/services/reservation.py
import asyncio
import json
import uuid
from domain.state_machine import TableState
from repository import tables as table_repo
from repository import reservations as res_repo
from repository import orders as order_repo
from repository import inventory as inventory_repo
from repository.elastic_mock import sync_to_elastic
from services.billing import calculate_table_cost, calculate_cancellation_fee
from database import get_reservations_db, get_inventory_db

TABLE_LOCKS = {}
HOLD_TIMERS = {}

class ConflictError(Exception):
    pass

class InsufficientIngredientsError(Exception):
    pass

class ReservationService:

    @staticmethod
    async def get_free_tables(date: str, start_time: str, end_time: str) -> list:
        all_tables = await table_repo.get_all_tables()
        busy_ids = await res_repo.get_busy_table_ids(date, start_time, end_time)
        return [t for t in all_tables if t["id"] not in busy_ids]

    @staticmethod
    async def hold_table(table_id: str, user_id: str, date: str, start_time: str, end_time: str) -> dict:
        lock = TABLE_LOCKS.setdefault(table_id, asyncio.Lock())
        async with lock:
            table = await table_repo.get_table_by_id(table_id)
            if not table:
                raise ValueError("Table not found")

            # Очистка всех устаревших HOLD для этого стола
            db = await get_reservations_db()
            await db.execute("UPDATE bookings SET status = 'EXPIRED' WHERE table_id = ? AND status = 'HOLD'", (table_id,))
            await db.commit()
            await db.close()

            # Проверка реальных пересечений с активными бронями
            conflicts = await res_repo.get_conflicting_reservations(table_id, date, start_time, end_time)
            if conflicts:
                raise ConflictError("Time slot already booked")

            await table_repo.update_table_state(table_id, TableState.HOLD_15MIN)

            sh = int(start_time.split(":")[0])
            eh = int(end_time.split(":")[0])
            if end_time == "00:00":
                eh = 24
            duration = max(1, eh - sh)

            booking_id = await res_repo.create_reservation({
                "table_id": table_id,
                "user_id": user_id,
                "date": date,
                "start_time": start_time,
                "duration": duration,
                "status": "HOLD",
                "total_cost": 0,
                "food_order_id": None
            })

            ReservationService._start_hold_timer(table_id, booking_id)
            await sync_to_elastic(table_id, "HOLD_15MIN", date, f"{start_time}-{end_time}")

            return {"booking_id": booking_id, "table_id": table_id, "state": "HOLD_15MIN"}

    @staticmethod
    def _start_hold_timer(table_id: str, booking_id: int):
        async def timer_task():
            await asyncio.sleep(15 * 60)
            try:
                booking = await res_repo.get_booking_by_id(booking_id)
                if booking and booking["status"] == "HOLD":
                    await table_repo.update_table_state(table_id, TableState.FREE)
                    await res_repo.update_reservation_status(booking_id, "EXPIRED")
                    await sync_to_elastic(table_id, "FREE")
            except Exception as e:
                print(f"Hold timer error: {e}")

        if table_id in HOLD_TIMERS:
            HOLD_TIMERS[table_id].cancel()
        HOLD_TIMERS[table_id] = asyncio.create_task(timer_task())

    @staticmethod
    async def confirm_reservation(table_id: str, user_id: str, payment_success: bool, food_items: list) -> dict:
        if not payment_success:
            raise ValueError("Payment failed")

        table = await table_repo.get_table_by_id(table_id)
        if not table or table["state"] != "HOLD_15MIN":
            raise ValueError("Invalid table state for confirmation")

        booking = await res_repo.get_active_hold(table_id)
        if not booking:
            raise ValueError("No active HOLD found")
        if booking["user_id"] != user_id:
            raise ValueError("User mismatch")

        booking_id = booking["id"]
        duration = booking["duration"]
        table_cost = calculate_table_cost(duration)

        db_res = await get_reservations_db()
        db_inv = await get_inventory_db()
        await db_res.execute("BEGIN IMMEDIATE")
        await db_inv.execute("BEGIN IMMEDIATE")
        try:
            food_cost = 0.0
            food_order_id = None
            if food_items:
                if not await inventory_repo.check_and_deduct_ingredients(db_inv, food_items):
                    raise InsufficientIngredientsError("Недостаточно ингредиентов на складе")

                for item in food_items:
                    cur = await db_inv.execute("SELECT name, price FROM meals WHERE id = ?", (int(item["menu_id"]),))
                    meal_row = await cur.fetchone()
                    if not meal_row:
                        raise ValueError(f"Meal with id {item['menu_id']} not found")
                    name = meal_row["name"]
                    price = meal_row["price"]
                    food_cost += price * item["qty"]

                    await db_res.execute(
                        "INSERT INTO order_items (booking_id, item_name, quantity) VALUES (?, ?, ?)",
                        (booking_id, name, item["qty"])
                    )

                order_id = str(uuid.uuid4())
                await db_res.execute(
                    "INSERT INTO food_orders (id, booking_id, status, items_json, total_food_cost) VALUES (?, ?, ?, ?, ?)",
                    (order_id, booking_id, "PENDING", json.dumps(food_items), food_cost)
                )
                food_order_id = order_id

            total_paid = table_cost + food_cost

            await db_res.execute(
                "UPDATE bookings SET status = 'RESERVED', total_cost = ?, food_order_id = ? WHERE id = ?",
                (total_paid, food_order_id, booking_id)
            )
            await db_res.execute("UPDATE tables SET state = 'RESERVED' WHERE id = ?", (table_id,))

            await db_res.commit()
            await db_inv.commit()
        except InsufficientIngredientsError:
            await db_res.execute("ROLLBACK")
            await db_inv.execute("ROLLBACK")
            raise
        except Exception as e:
            await db_res.execute("ROLLBACK")
            await db_inv.execute("ROLLBACK")
            raise e
        finally:
            await db_res.close()
            await db_inv.close()

        if table_id in HOLD_TIMERS:
            HOLD_TIMERS[table_id].cancel()
            del HOLD_TIMERS[table_id]

        await sync_to_elastic(table_id, "RESERVED", booking["date"],
                              f"{booking['start_time']} + {booking['duration']}h")

        return {
            "booking_id": booking_id,
            "total_paid": total_paid,
            "status": "RESERVED",
            "food_order_id": food_order_id
        }

    @staticmethod
    async def release_hold(table_id: str, user_id: str) -> bool:
        """Мгновенное освобождение стола при выходе из процесса бронирования."""
        db = await get_reservations_db()
        cursor = await db.execute(
            "SELECT id FROM bookings WHERE table_id = ? AND user_id = ? AND status = 'HOLD' ORDER BY id DESC LIMIT 1",
            (table_id, user_id)
        )
        row = await cursor.fetchone()
        await db.close()
        if not row:
            return False

        booking_id = row["id"]
        if table_id in HOLD_TIMERS:
            HOLD_TIMERS[table_id].cancel()
            del HOLD_TIMERS[table_id]

        await res_repo.update_reservation_status(booking_id, "EXPIRED")
        await table_repo.update_table_state(table_id, TableState.FREE)
        await sync_to_elastic(table_id, "FREE")
        return True

    @staticmethod
    async def cancel_reservation(table_id: str, user_id: str) -> dict:
        db = await get_reservations_db()
        cursor = await db.execute(
            "SELECT * FROM bookings WHERE table_id = ? AND user_id = ? AND status IN ('HOLD','RESERVED') ORDER BY id DESC LIMIT 1",
            (table_id, user_id)
        )
        row = await cursor.fetchone()
        if not row:
            raise ValueError("No active reservation found")
        booking = dict(row)
        booking_id = booking["id"]
        await db.close()

        table = await table_repo.get_table_by_id(table_id)
        if not table:
            raise ValueError("Table not found")

        penalty_info = await calculate_cancellation_fee(booking)

        await res_repo.update_reservation_status(booking_id, "CANCELED")
        await table_repo.update_table_state(table_id, TableState.FREE)

        if table_id in HOLD_TIMERS:
            HOLD_TIMERS[table_id].cancel()
            del HOLD_TIMERS[table_id]

        await sync_to_elastic(table_id, "FREE")
        return penalty_info

    @staticmethod
    async def get_user_reservations(user_id: str) -> list:
        bookings = await res_repo.get_user_reservations(user_id)
        result = []
        for b in bookings:
            items_list = await res_repo.get_order_items_for_booking(b["id"])
            items_str = ", ".join(f"{it['quantity']}x {it['item_name']}" for it in items_list) if items_list else ""
            start_h = int(b["start_time"].split(":")[0])
            end_h = start_h + b["duration"]
            if end_h >= 24:
                end_h = 24
            time_slot = f"{b['start_time']}-{end_h:02d}:00"
            result.append({
                "booking_id": b["id"],
                "table_id": b["table_id"],
                "date": b["date"],
                "time_slot": time_slot,
                "status": b["status"],
                "total_cost": b["total_cost"],
                "items": items_str
            })
        return result

    @staticmethod
    async def cancel_booking_by_id(booking_id: int, user_id: str) -> dict:
        booking = await res_repo.get_booking_by_id(booking_id)
        if not booking or booking["user_id"] != user_id:
            raise ValueError("Booking not found or not owned")
        table_id = booking["table_id"]
        penalty = await calculate_cancellation_fee(booking)
        await res_repo.update_reservation_status(booking_id, "CANCELED")
        await table_repo.update_table_state(table_id, TableState.FREE)
        if table_id in HOLD_TIMERS:
            HOLD_TIMERS[table_id].cancel()
            del HOLD_TIMERS[table_id]
        await sync_to_elastic(table_id, "FREE")
        return penalty