# backend/database.py
import aiosqlite
from domain.user import hash_password

INVENTORY_DB = "inventory.db"
RESERVATIONS_DB = "reservations.db"

async def get_inventory_db() -> aiosqlite.Connection:
    db = await aiosqlite.connect(INVENTORY_DB)
    db.row_factory = aiosqlite.Row
    await db.execute("PRAGMA journal_mode=WAL")
    await db.execute("PRAGMA foreign_keys=ON")
    return db

async def get_reservations_db() -> aiosqlite.Connection:
    db = await aiosqlite.connect(RESERVATIONS_DB)
    db.row_factory = aiosqlite.Row
    await db.execute("PRAGMA journal_mode=WAL")
    await db.execute("PRAGMA foreign_keys=ON")
    return db

async def init_databases():
    # Инициализация inventory.db (склад + меню + рецепты)
    db_inv = await get_inventory_db()
    await db_inv.executescript("""
        CREATE TABLE IF NOT EXISTS stock (
            item_keyword TEXT PRIMARY KEY,
            quantity INTEGER NOT NULL DEFAULT 0
        );
        CREATE TABLE IF NOT EXISTS meals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            price INTEGER NOT NULL
        );
        CREATE TABLE IF NOT EXISTS recipes (
            meal_id INTEGER NOT NULL,
            ingredient_keyword TEXT NOT NULL,
            quantity_needed INTEGER NOT NULL,
            PRIMARY KEY (meal_id, ingredient_keyword),
            FOREIGN KEY (meal_id) REFERENCES meals(id),
            FOREIGN KEY (ingredient_keyword) REFERENCES stock(item_keyword)
        );
    """)
    await db_inv.commit()

    # Начальные данные склада
    cursor = await db_inv.execute("SELECT COUNT(*) FROM stock")
    if (await cursor.fetchone())[0] == 0:
        stock_data = [
            ("meat", 5000), ("rice", 10000), ("carrot", 8000),
            ("onion", 3000), ("oil", 5000), ("coca_cola", 30), ("kompot", 20)
        ]
        await db_inv.executemany("INSERT INTO stock (item_keyword, quantity) VALUES (?, ?)", stock_data)
        await db_inv.commit()

    # Начальные блюда и рецепты
    cursor = await db_inv.execute("SELECT COUNT(*) FROM meals")
    if (await cursor.fetchone())[0] == 0:
        await db_inv.execute("INSERT INTO meals (id, name, price) VALUES (1, 'Плов Ташкентский', 45000)")
        await db_inv.execute("INSERT INTO meals (id, name, price) VALUES (2, 'Шашлык Ассорти', 35000)")
        await db_inv.execute("INSERT INTO meals (id, name, price) VALUES (3, 'Coca-Cola 0.5L', 10000)")
        await db_inv.execute("INSERT INTO meals (id, name, price) VALUES (4, 'Компот Домашний', 12000)")
        recipes_data = [
            (1, "meat", 500), (1, "rice", 1000), (1, "carrot", 1000), (1, "onion", 200), (1, "oil", 1000),
            (2, "meat", 400), (2, "onion", 100),
            (3, "coca_cola", 1),
            (4, "kompot", 1)
        ]
        await db_inv.executemany("INSERT INTO recipes (meal_id, ingredient_keyword, quantity_needed) VALUES (?, ?, ?)", recipes_data)
        await db_inv.commit()
    await db_inv.close()

    # Инициализация reservations.db (столы, брони, заказы, пользователи)
    db_res = await get_reservations_db()
    await db_res.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            username TEXT PRIMARY KEY,
            password_hash TEXT NOT NULL,
            role TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS auth_tokens (
            token TEXT PRIMARY KEY,
            username TEXT NOT NULL,
            FOREIGN KEY (username) REFERENCES users(username)
        );
        CREATE TABLE IF NOT EXISTS tables (
            id TEXT PRIMARY KEY,
            capacity INTEGER NOT NULL,
            state TEXT DEFAULT 'FREE'
        );
        CREATE TABLE IF NOT EXISTS bookings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            table_id TEXT NOT NULL,
            user_id TEXT NOT NULL,
            date TEXT NOT NULL,
            start_time TEXT NOT NULL,
            duration INTEGER NOT NULL,
            status TEXT DEFAULT 'HOLD',
            total_cost REAL DEFAULT 0,
            food_order_id TEXT,
            FOREIGN KEY (table_id) REFERENCES tables(id)
        );
        CREATE TABLE IF NOT EXISTS order_items (
            booking_id INTEGER NOT NULL,
            item_name TEXT,
            quantity INTEGER NOT NULL,
            FOREIGN KEY (booking_id) REFERENCES bookings(id)
        );
        CREATE TABLE IF NOT EXISTS food_orders (
            id TEXT PRIMARY KEY,
            booking_id INTEGER,
            status TEXT DEFAULT 'PENDING',
            items_json TEXT,
            total_food_cost REAL DEFAULT 0,
            FOREIGN KEY (booking_id) REFERENCES bookings(id)
        );
    """)
    await db_res.commit()

    # Админ по умолчанию
    cursor = await db_res.execute("SELECT COUNT(*) FROM users WHERE username = 'admin'")
    if (await cursor.fetchone())[0] == 0:
        await db_res.execute(
            "INSERT INTO users (username, password_hash, role) VALUES (?, ?, ?)",
            ("admin", hash_password("admin"), "admin")
        )
        await db_res.commit()

    # Официант по умолчанию (до закрытия БД!)
    cursor = await db_res.execute("SELECT COUNT(*) FROM users WHERE username = 'waiter'")
    if (await cursor.fetchone())[0] == 0:
        await db_res.execute(
            "INSERT INTO users (username, password_hash, role) VALUES (?, ?, ?)",
            ("waiter", hash_password("waiter"), "waiter")
        )
        # Фиксированный токен для простоты
        await db_res.execute(
            "INSERT INTO auth_tokens (token, username) VALUES (?, ?)",
            ("waiter_token", "waiter")
        )
        await db_res.commit()

    # Столы (10 шт.)
    cursor = await db_res.execute("SELECT COUNT(*) FROM tables")
    if (await cursor.fetchone())[0] == 0:
        for i in range(1, 11):
            await db_res.execute(
                "INSERT INTO tables (id, capacity, state) VALUES (?, 4, 'FREE')",
                (f"T{i}",)
            )
        await db_res.commit()

        # Шеф-повар по умолчанию
    cursor = await db_res.execute("SELECT COUNT(*) FROM users WHERE username = 'chef'")
    if (await cursor.fetchone())[0] == 0:
        await db_res.execute(
            "INSERT INTO users (username, password_hash, role) VALUES (?, ?, ?)",
            ("chef", hash_password("chef"), "chef")
        )
        # Фиксированный токен
        await db_res.execute(
            "INSERT INTO auth_tokens (token, username) VALUES (?, ?)",
            ("chef_token", "chef")
        )
        await db_res.commit()


    await db_res.close()

    