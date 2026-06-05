# backend/repository/inventory.py
from database import get_inventory_db

# --- Stock ---
async def get_full_stock():
    db = await get_inventory_db()
    cursor = await db.execute("SELECT item_keyword, quantity FROM stock")
    rows = await cursor.fetchall()
    await db.close()
    return {row["item_keyword"]: row["quantity"] for row in rows}

async def add_stock(item: str, quantity: int):
    db = await get_inventory_db()
    await db.execute(
        "INSERT INTO stock (item_keyword, quantity) VALUES (?, ?) ON CONFLICT(item_keyword) DO UPDATE SET quantity = quantity + EXCLUDED.quantity",
        (item, quantity)
    )
    await db.commit()
    await db.close()

async def ensure_ingredient_exists(db, keyword: str):
    """Вставить ингредиент с 0, если его нет (в рамках переданной транзакции)."""
    await db.execute(
        "INSERT OR IGNORE INTO stock (item_keyword, quantity) VALUES (?, 0)",
        (keyword,)
    )

# --- Meals ---
async def get_all_meals():
    db = await get_inventory_db()
    # Получаем блюда с их рецептами
    cursor = await db.execute("SELECT id, name, price FROM meals")
    meals = [dict(row) for row in await cursor.fetchall()]
    for meal in meals:
        # Загружаем рецепт
        cur = await db.execute(
            "SELECT ingredient_keyword, quantity_needed FROM recipes WHERE meal_id = ?",
            (meal["id"],)
        )
        recipes = await cur.fetchall()
        meal["recipe"] = {r["ingredient_keyword"]: r["quantity_needed"] for r in recipes}
        # ingredients_text
        meal["ingredients_text"] = ", ".join(
            f"{r['ingredient_keyword']}: {r['quantity_needed']}г" for r in recipes
        )
    await db.close()
    return meals

async def create_meal(name: str, price: int, recipe: dict):
    """Создаёт блюдо, ингредиенты (при необходимости) и рецепты."""
    db = await get_inventory_db()
    await db.execute("BEGIN IMMEDIATE")
    try:
        # Вставляем блюдо
        cursor = await db.execute("INSERT INTO meals (name, price) VALUES (?, ?)", (name, price))
        meal_id = cursor.lastrowid
        # Добавляем ингредиенты в stock, если их нет
        for ingredient in recipe:
            await ensure_ingredient_exists(db, ingredient)
        # Вставляем рецепты
        for ingredient, qty in recipe.items():
            await db.execute(
                "INSERT INTO recipes (meal_id, ingredient_keyword, quantity_needed) VALUES (?, ?, ?)",
                (meal_id, ingredient, qty)
            )
        await db.commit()
        await db.close()
        return meal_id
    except Exception as e:
        await db.execute("ROLLBACK")
        await db.close()
        raise e

async def update_meal(meal_id: int, name: str, price: int, recipe: dict):
    """Обновляет блюдо и его рецепты."""
    db = await get_inventory_db()
    await db.execute("BEGIN IMMEDIATE")
    try:
        await db.execute("UPDATE meals SET name = ?, price = ? WHERE id = ?", (name, price, meal_id))
        # Удаляем старые рецепты
        await db.execute("DELETE FROM recipes WHERE meal_id = ?", (meal_id,))
        # Добавляем ингредиенты в stock при необходимости
        for ingredient in recipe:
            await ensure_ingredient_exists(db, ingredient)
        # Вставляем новые рецепты
        for ingredient, qty in recipe.items():
            await db.execute(
                "INSERT INTO recipes (meal_id, ingredient_keyword, quantity_needed) VALUES (?, ?, ?)",
                (meal_id, ingredient, qty)
            )
        await db.commit()
        await db.close()
    except Exception as e:
        await db.execute("ROLLBACK")
        await db.close()
        raise e

async def delete_meal(meal_id: int):
    db = await get_inventory_db()
    await db.execute("DELETE FROM meals WHERE id = ?", (meal_id,))
    await db.execute("DELETE FROM recipes WHERE meal_id = ?", (meal_id,))
    await db.commit()
    await db.close()

async def check_and_deduct_ingredients(db, food_items: list) -> bool:
    """Проверяет и списывает ингредиенты в рамках переданной транзакции (db - inventory.db соединение)."""
    needed = {}
    for item in food_items:
        meal_id = int(item["menu_id"])
        qty = item["qty"]
        cursor = await db.execute(
            "SELECT ingredient_keyword, quantity_needed FROM recipes WHERE meal_id = ?",
            (meal_id,)
        )
        rows = await cursor.fetchall()
        for row in rows:
            ing = row["ingredient_keyword"]
            per_item = row["quantity_needed"]
            needed[ing] = needed.get(ing, 0) + per_item * qty

    for ing, required in needed.items():
        cursor = await db.execute("SELECT quantity FROM stock WHERE item_keyword = ?", (ing,))
        row = await cursor.fetchone()
        if not row or row["quantity"] < required:
            return False

    for ing, required in needed.items():
        await db.execute("UPDATE stock SET quantity = quantity - ? WHERE item_keyword = ?", (required, ing))
    return True