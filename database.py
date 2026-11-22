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
                bio TEXT,
                photo_id TEXT
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS likes (
                from_user INTEGER,
                to_user INTEGER,
                is_like BOOLEAN,
                PRIMARY KEY (from_user, to_user)
            )
        """)
        await db.commit()

async def add_user(user_id, username, name, age, gender, target_gender, bio, photo_id):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("""
            INSERT OR REPLACE INTO users (user_id, username, name, age, gender, target_gender, bio, photo_id)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (user_id, username, name, age, gender, target_gender, bio, photo_id))
        await db.commit()

async def get_next_profile(user_id):
    async with aiosqlite.connect(DB_NAME) as db:
        cursor = await db.execute("SELECT target_gender FROM users WHERE user_id = ?", (user_id,))
        row = await cursor.fetchone()
        if not row:
            return None
        target_gender = row[0]

        cursor = await db.execute("""
            SELECT user_id, name, age, bio, photo_id FROM users
            WHERE user_id != ?
              AND gender = ?
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

async def get_username(user_id):
    async with aiosqlite.connect(DB_NAME) as db:
        cursor = await db.execute("SELECT username, name FROM users WHERE user_id = ?", (user_id,))
        return await cursor.fetchone()
