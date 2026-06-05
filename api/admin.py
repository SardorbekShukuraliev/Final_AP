# backend/api/admin.py
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from auth import require_role
from repository import inventory as inv_repo
from services.admin_service import get_audit_data, get_table_history

router = APIRouter(dependencies=[Depends(require_role("admin"))])

# --- Склад ---
@router.get("/stock")
async def get_stock():
    return await inv_repo.get_full_stock()

@router.post("/stock/buy")
async def buy_stock(item: str = Query(...), quantity: int = Query(...)):
    if quantity <= 0:
        raise HTTPException(400, "Quantity must be positive")
    await inv_repo.add_stock(item, quantity)
    return await inv_repo.get_full_stock()

# --- CRUD блюд ---
@router.get("/meals")
async def get_meals():
    return await inv_repo.get_all_meals()

class MealCreate(BaseModel):
    name: str
    price: int
    recipe: dict  # {"ingredient": quantity}

@router.post("/meals")
async def create_meal(meal: MealCreate):
    try:
        meal_id = await inv_repo.create_meal(meal.name, meal.price, meal.recipe)
        return {"id": meal_id}
    except Exception as e:
        raise HTTPException(500, str(e))

@router.put("/meals/{meal_id}")
async def update_meal(meal_id: int, meal: MealCreate):
    try:
        await inv_repo.update_meal(meal_id, meal.name, meal.price, meal.recipe)
        return {"message": "updated"}
    except Exception as e:
        raise HTTPException(500, str(e))

@router.delete("/meals/{meal_id}")
async def delete_meal(meal_id: int):
    await inv_repo.delete_meal(meal_id)
    return {"message": "deleted"}

# --- Аудит столов ---
@router.get("/tables/audit")
async def audit_tables():
    return await get_audit_data()

@router.get("/tables/{table_id}/history")
async def table_history(table_id: str):
    return await get_table_history(table_id)