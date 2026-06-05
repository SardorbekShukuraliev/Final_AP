# backend/repository/tables.py
from database import get_reservations_db
from domain.state_machine import TableState

async def get_all_tables():
    db = await get_reservations_db()
    cursor = await db.execute("SELECT id, capacity, state FROM tables")
    rows = await cursor.fetchall()
    await db.close()
    return [dict(row) for row in rows]

async def get_table_by_id(table_id: str):
    db = await get_reservations_db()
    cursor = await db.execute("SELECT id, capacity, state FROM tables WHERE id = ?", (table_id,))
    row = await cursor.fetchone()
    await db.close()
    return dict(row) if row else None

async def update_table_state(table_id: str, new_state: TableState):
    db = await get_reservations_db()
    await db.execute("UPDATE tables SET state = ? WHERE id = ?", (new_state.value, table_id))
    await db.commit()
    await db.close()