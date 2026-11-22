import math
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
                lat REAL,
                lon REAL,
                bio TEXT,
                photo_id TEXT,
                is_banned BOOLEAN DEFAULT 0
            )
        """)
        for col in [
            "ALTER TABLE users ADD COLUMN lat REAL",
            "ALTER TABLE users ADD COLUMN lon REAL",
            "ALTER TABLE users ADD COLUMN is_banned BOOLEAN DEFAULT 0"
        ]:
            try:
                await db.execute(col)
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

async def add_user(user_id, username, name, age, gender, target_gender, lat, lon, bio, photo_id):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("""
            INSERT OR REPLACE INTO users (user_id, username, name, age, gender, target_gender, lat, lon, bio, photo_id, is_banned)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0)
        """, (user_id, username, name, age, gender, target_gender, lat, lon, bio, photo_id))
        await db.commit()

async def update_location(user_id, lat, lon):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("UPDATE users SET lat = ?, lon = ? WHERE user_id = ?", (lat, lon, user_id))
        await db.commit()

async def get_user(user_id):
    async with aiosqlite.connect(DB_NAME) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
        row = await cursor.fetchone()
        return dict(row) if row else None

def calc_distance(lat1, lon1, lat2, lon2):
    if None in (lat1, lon1, lat2, lon2):
        return None
    r = 6371.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    dist = 2 * r * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    if dist < 1:
        return "менее 1 км"
    return f"{round(dist)} км"

async def get_next_profile(user_id):
    me = await get_user(user_id)
    if not me or me.get("is_banned"):
        return None

    async with aiosqlite.connect(DB_NAME) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("""
            SELECT user_id, name, age, lat, lon, bio, photo_id FROM users
            WHERE user_id != ?
              AND gender = ?
              AND is_banned = 0
              AND user_id NOT IN (SELECT to_user FROM likes WHERE from_user = ?)
        """, (user_id, me["target_gender"], user_id))
        rows = await cursor.fetchall()
        if not rows:
            return None

        profiles = [dict(r) for r in rows]
        # Сортируем анкеты от ближайших к дальним
        profiles.sort(key=lambda p: (
            calc_distance_num(me.get("lat"), me.get("lon"), p.get("lat"), p.get("lon"))
        ))
        best = profiles
        best["distance_str"] = calc_distance(me.get("lat"), me.get("lon"), best.get("lat"), best.get("lon"))
        return best

def calc_distance_num(lat1, lon1, lat2, lon2):
    if None in (lat1, lon1, lat2, lon2):
        return 999999.0
    r = 6371.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return 2 * r * math.atan2(math.sqrt(a), math.sqrt(1 - a))

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
