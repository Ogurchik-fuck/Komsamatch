import aiosqlite

DB_NAME = "dating.db"

async def init_db():
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                name TEXT,
                age INTEGER,
                gender TEXT,
                target_gender TEXT,
                district TEXT,
                bio TEXT,
                photo_id TEXT,
                is_banned BOOLEAN DEFAULT 0
            )
        """)
        # Добавляем колонки, если база осталась от старой версии
        try:
            await db.execute("ALTER TABLE users ADD COLUMN district TEXT DEFAULT 'Не указан'")
        except Exception:
            pass
        try:
            await db.execute("ALTER TABLE users ADD COLUMN is_banned BOOLEAN DEFAULT 0")
        except Exception:
            pass

        await db.execute("""
            CREATE TABLE IF NOT EXISTS likes (
                from_user INTEGER,
                to_user INTEGER,
                is_like BOOLEAN,
                PRIMARY KEY (from_user, to_user)
            )
        """)
        await db.commit()

async def add_user(user_id, username, name, age, gender, target_gender, district, bio, photo_id):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("""
            INSERT OR REPLACE INTO users (user_id, username, name, age, gender, target_gender, district, bio, photo_id, is_banned)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 0)
        """, (user_id, username, name, age, gender, target_gender, district, bio, photo_id))
        await db.commit()

async def get_user(user_id):
    async with aiosqlite.connect(DB_NAME) as db:
        cursor = await db.execute(
            "SELECT user_id, username, name, age, gender, target_gender, district, bio, photo_id, is_banned FROM users WHERE user_id = ?",
            (user_id,)
        )
        return await cursor.fetchone()

async def get_next_profile(user_id):
    async with aiosqlite.connect(DB_NAME) as db:
        cursor = await db.execute("SELECT target_gender, is_banned FROM users WHERE user_id = ?", (user_id,))
        row = await cursor.fetchone()
        if not row or row[1]:
            return None
        target_gender = row[0]

        cursor = await db.execute("""
            SELECT user_id, name, age, district, bio, photo_id FROM users
            WHERE user_id != ?
              AND gender = ?
              AND is_banned = 0
              AND user_id NOT IN (SELECT to_user FROM likes WHERE from_user = ?)
            LIMIT 1
        """, (user_id, target_gender, user_id))
        return await cursor.fetchone()

async def add_like(from_user, to_user, is_like: bool) -> bool:
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute(
            "INSERT OR REPLACE INTO likes (from_user, to_user, is_like) VALUES (?, ?, ?)",
            (from_user, to_user, is_like)
        )
        await db.commit()

        if is_like:
            cursor = await db.execute(
                "SELECT is_like FROM likes WHERE from_user = ? AND to_user = ? AND is_like = 1",
                (to_user, from_user)
            )
            mutual = await cursor.fetchone()
            return bool(mutual)
        return False

async def ban_user(user_id):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("UPDATE users SET is_banned = 1 WHERE user_id = ?", (user_id,))
        await db.commit()
