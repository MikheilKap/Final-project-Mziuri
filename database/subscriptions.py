import aiosqlite
from datetime import date

from database.db_config import DB_PATH


async def upsert_subscription(user_id: int, sub: dict) -> str:
    """Insert or update a subscription. Returns 'added' or 'updated'.
    Also records a history snapshot for trend analysis."""
    today = date.today().isoformat()

    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "SELECT id, cost, cycle FROM subscriptions WHERE user_id = ? AND LOWER(name) = LOWER(?)",
            (user_id, sub["name"]),
        )
        row = await cursor.fetchone()

        currency = sub.get("currency") or "USD"
        category = sub.get("category") or "Other"

        if row:
            sub_id, old_cost, old_cycle = row
            await db.execute(
                """UPDATE subscriptions
                   SET cost = ?, currency = ?, cycle = ?, method = ?, renewal_date = ?, category = ?
                   WHERE id = ? AND user_id = ?""",
                (
                    sub["cost"],
                    currency,
                    sub["cycle"],
                    sub["method"],
                    sub.get("renewal_date"),
                    category,
                    sub_id,
                    user_id,
                ),
            )

            await db.execute(
                """INSERT INTO subscription_history
                   (subscription_id, user_id, name, cost, cycle, renewal_date, recorded_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (sub_id, user_id, sub["name"], sub["cost"], sub["cycle"],
                 sub.get("renewal_date"), today),
            )
            await db.commit()
            return "updated"

        cursor = await db.execute(
            """INSERT INTO subscriptions (name, cost, currency, cycle, method, renewal_date, category, user_id, first_detected)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                sub["name"],
                sub["cost"],
                currency,
                sub["cycle"],
                sub["method"],
                sub.get("renewal_date"),
                category,
                user_id,
                today,
            ),
        )
        sub_id = cursor.lastrowid

        await db.execute(
            """INSERT INTO subscription_history
               (subscription_id, user_id, name, cost, cycle, renewal_date, recorded_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (sub_id, user_id, sub["name"], sub["cost"], sub["cycle"],
             sub.get("renewal_date"), today),
        )
        await db.commit()
        return "added"


async def import_subscriptions(user_id: int, subs: list[dict]) -> dict:
    added = []
    updated = []
    for sub in subs:
        action = await upsert_subscription(user_id, sub)
        if action == "added":
            added.append(sub)
        else:
            updated.append(sub)
    return {"added": added, "updated": updated}
