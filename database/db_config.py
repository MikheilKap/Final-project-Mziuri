import os
import aiosqlite

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "subtracker.db")


async def _column_exists(db, table: str, column: str) -> bool:
    cursor = await db.execute(f"PRAGMA table_info({table})")
    rows = await cursor.fetchall()
    return any(row[1] == column for row in rows)


async def _table_exists(db, table: str) -> bool:
    cursor = await db.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table,)
    )
    return await cursor.fetchone() is not None


async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password TEXT NOT NULL,
                email TEXT UNIQUE,
                avatar TEXT DEFAULT 'fox'
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS subscriptions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                cost REAL NOT NULL,
                currency TEXT DEFAULT 'USD',
                cycle TEXT NOT NULL,
                method TEXT NOT NULL,
                renewal_date TEXT,
                category TEXT DEFAULT 'Other',
                user_id INTEGER,
                first_detected TEXT,
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
        """)

        await db.execute("""
            CREATE TABLE IF NOT EXISTS subscription_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                subscription_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                name TEXT NOT NULL,
                cost REAL NOT NULL,
                cycle TEXT NOT NULL,
                renewal_date TEXT,
                recorded_at TEXT NOT NULL,
                FOREIGN KEY (subscription_id) REFERENCES subscriptions(id),
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
        """)
        await db.commit()

        migrations = [
            ("users", "email", "ALTER TABLE users ADD COLUMN email TEXT"),
            ("users", "avatar", "ALTER TABLE users ADD COLUMN avatar TEXT DEFAULT 'fox'"),
            ("subscriptions", "user_id", "ALTER TABLE subscriptions ADD COLUMN user_id INTEGER"),
            ("subscriptions", "renewal_date", "ALTER TABLE subscriptions ADD COLUMN renewal_date TEXT"),
            ("subscriptions", "first_detected", "ALTER TABLE subscriptions ADD COLUMN first_detected TEXT"),
            ("subscriptions", "currency", "ALTER TABLE subscriptions ADD COLUMN currency TEXT DEFAULT 'USD'"),
            ("subscriptions", "category", "ALTER TABLE subscriptions ADD COLUMN category TEXT DEFAULT 'Other'"),
        ]
        for table, column, sql in migrations:
            if not await _column_exists(db, table, column):
                await db.execute(sql)
                await db.commit()

        await db.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS idx_users_email ON users(email)"
        )
        await db.commit()
