import aiosqlite

from database.auth import get_user_id, get_username
from database.avatars import AVATARS, get_avatar_info
from database.db_config import DB_PATH


async def fetch_user(user_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT id, username, email, avatar FROM users WHERE id = ?",
            (user_id,),
        )
        return await cursor.fetchone()


async def build_template_context(request, **extra):
    user_id = get_user_id(request)
    user = await fetch_user(user_id) if user_id else None
    avatar = get_avatar_info(user["avatar"] if user else None)
    return {
        "request": request,
        "user_id": user_id,
        "username": get_username(request),
        "user_email": user["email"] if user else None,
        "avatar": avatar,
        "avatars": AVATARS,
        **extra,
    }
