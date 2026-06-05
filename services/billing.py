# backend/services/billing.py
from repository import orders as order_repo

BASE_HOURLY_RATE = 20000

def calculate_table_cost(hours: int) -> float:
    return hours * BASE_HOURLY_RATE

async def calculate_food_total(food_items: list) -> float:
    return 0.0  # Заглушка, не используется в основной логике

async def calculate_cancellation_fee(reservation: dict) -> dict:
    food_order_id = reservation.get("food_order_id")
    total_paid = reservation.get("total_cost", 0)
    food_cost = 0.0
    food_status = "PENDING"
    if food_order_id:
        order = await order_repo.get_food_order(food_order_id)
        if order:
            food_cost = order["total_food_cost"]
            food_status = order["status"]
    table_cost = total_paid - food_cost
    table_penalty_pct = 0.2
    table_fee = table_cost * table_penalty_pct
    food_refund = food_cost
    food_penalty = 0.0
    if food_status in ("PREPARING", "READY"):
        food_refund = 0.0
        food_penalty = food_cost
    total_refund = (table_cost - table_fee) + food_refund
    total_penalty = table_fee + food_penalty
    return {
        "refund_amount": total_refund,
        "penalty": total_penalty,
        "table_fee": table_fee,
        "food_refund": food_refund,
        "food_penalty": food_penalty
    }