# backend/services/menu_service.py
from database import get_inventory_db

async def get_available_menu():
    """
    Возвращает список блюд (из таблицы meals в inventory.db),
    для которых ВСЕ ингредиенты есть в достаточном количестве.
    """
    db = await get_inventory_db()

    # Получаем все блюда
    cursor = await db.execute("SELECT id, name, price FROM meals")
    meals = [dict(row) for row in await cursor.fetchall()]

    # Получаем все рецепты
    cursor = await db.execute("SELECT meal_id, ingredient_keyword, quantity_needed FROM recipes")
    recipe_rows = await cursor.fetchall()

    # Группируем требования по meal_id
    requirements = {}
    for r in recipe_rows:
        mid = r["meal_id"]
        if mid not in requirements:
            requirements[mid] = []
        requirements[mid].append((r["ingredient_keyword"], r["quantity_needed"]))

    # Текущие остатки на складе
    cursor = await db.execute("SELECT item_keyword, quantity FROM stock")
    stock = {row["item_keyword"]: row["quantity"] for row in await cursor.fetchall()}

    available = []
    for meal in meals:
        mid = meal["id"]
        if mid in requirements:
            enough = True
            for ing, needed in requirements[mid]:
                if stock.get(ing, 0) < needed:
                    enough = False
                    break
            if enough:
                available.append(meal)
        else:
            # Блюдо без рецепта всегда доступно
            available.append(meal)

    await db.close()
    return available