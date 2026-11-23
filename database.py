import math
import json
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
                location_text TEXT DEFAULT 'г. Комсомольск-на-Амуре',
                bio TEXT DEFAULT '',
                photos TEXT,
                video_id TEXT,
                video_type TEXT,
                is_active BOOLEAN DEFAULT 1,
                is_banned BOOLEAN DEFAULT 0,
                views_count INTEGER DEFAULT 0,
                bio_prompted BOOLEAN DEFAULT 0
            )
        """)
        for col in [
            "ALTER TABLE users ADD COLUMN photos TEXT",
            "ALTER TABLE users ADD COLUMN video_id TEXT",
            "ALTER TABLE users ADD COLUMN video_type TEXT",
            "ALTER TABLE users ADD COLUMN is_active BOOLEAN DEFAULT 1",
            "ALTER TABLE users ADD COLUMN is_banned BOOLEAN DEFAULT 0",
            "ALTER TABLE users ADD COLUMN location_text TEXT DEFAULT 'г. Комсомольск-на-Амуре'",
            "ALTER TABLE users ADD COLUMN views_count INTEGER DEFAULT 0",
            "ALTER TABLE users ADD COLUMN bio_prompted BOOLEAN DEFAULT 0"
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

async def add_user(user_id, username, name, age, gender, target_gender, lat, lon, location_text, bio, photos_list, video_id=None, video_type=None):
    photos_json = json.dumps(photos_list)
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("""
            INSERT OR REPLACE INTO users 
            (user_id, username, name, age, gender, target_gender, lat, lon, location_text, bio, photos, video_id, video_type, is_active, is_banned, views_count, bio_prompted)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, 0, 0, 0)
        """, (user_id, username, name, age, gender, target_gender, lat, lon, location_text, bio or "", photos_json, video_id, video_type))
        await db.commit()

async def update_location(user_id, lat, lon, location_text):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("UPDATE users SET lat = ?, lon = ?, location_text = ? WHERE user_id = ?", (lat, lon, location_text, user_id))
        await db.commit()

async def update_bio(user_id, bio):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("UPDATE users SET bio = ?, bio_prompted = 1 WHERE user_id = ?", (bio, user_id))
        await db.commit()

async def increment_views_and_check_prompt(user_id) -> bool:
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("UPDATE users SET views_count = COALESCE(views_count, 0) + 1 WHERE user_id = ?", (user_id,))
        await db.commit()
        cursor = await db.execute("SELECT bio, views_count, bio_prompted FROM users WHERE user_id = ?", (user_id,))
        row = await cursor.fetchone()
        if not row:
            return False
        bio, views, prompted = row
        if (not bio or not bio.strip()) and views >= 12 and not prompted:
            await db.execute("UPDATE users SET bio_prompted = 1 WHERE user_id = ?", (user_id,))
            await db.commit()
            return True
        return False

async def set_active(user_id, is_active: bool):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("UPDATE users SET is_active = ? WHERE user_id = ?", (1 if is_active else 0, user_id))
        await db.commit()

async def get_user(user_id):
    async with aiosqlite.connect(DB_NAME) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
        row = await cursor.fetchone()
        if not row:
            return None
        user = dict(row)
        if user.get("photos"):
            user["photos_list"] = json.loads(user["photos"])
        elif user.get("photo_id"):
            user["photos_list"] = [user["photo_id"]]
        else:
            user["photos_list"] = []
        return user

def calc_distance_num(lat1, lon1, lat2, lon2):
    if None in (lat1, lon1, lat2, lon2):
        return 999999.0
    r = 6371.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return 2 * r * math.atan2(math.sqrt(a), math.sqrt(1 - a))

def format_place(me: dict, target: dict) -> str:
    if None not in (me.get("lat"), me.get("lon"), target.get("lat"), target.get("lon")):
        dist = calc_distance_num(me["lat"], me["lon"], target["lat"], target["lon"])
        return "менее 1 км от тебя" if dist < 1 else f"{round(dist)} км от тебя"
    return target.get("location_text") or "г. Комсомольск-на-Амуре"

async def get_next_profile(user_id):
    me = await get_user(user_id)
    if not me or me.get("is_banned") or not me.get("is_active", 1):
        return None

    async with aiosqlite.connect(DB_NAME) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("""
            SELECT * FROM users
            WHERE user_id != ?
              AND gender = ?
              AND is_banned = 0
              AND (is_active = 1 OR is_active IS NULL)
              AND user_id NOT IN (SELECT to_user FROM likes WHERE from_user = ?)
        """, (user_id, me["target_gender"], user_id))
        rows = await cursor.fetchall()
        if not rows:
            return None

        profiles = []
        for r in rows:
            p = dict(r)
            p["photos_list"] = json.loads(p["photos"]) if p.get("photos") else ([p["photo_id"]] if p.get("photo_id") else [])
            if p["photos_list"]:
                profiles.append(p)

        if not profiles:
            return None

        profiles.sort(key=lambda p: calc_distance_num(me.get("lat"), me.get("lon"), p.get("lat"), p.get("lon")))
        best = next(iter(profiles))
        best["distance_str"] = format_place(me, best)
        return best

async def get_incoming_like(user_id):
    me = await get_user(user_id)
    if not me:
        return None
    async with aiosqlite.connect(DB_NAME) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("""
            SELECT u.* FROM users u
            JOIN likes l ON u.user_id = l.from_user
            WHERE l.to_user = ?
              AND l.is_like = 1
              AND u.is_banned = 0
              AND u.user_id NOT IN (SELECT to_user FROM likes WHERE from_user = ?)
            LIMIT 1
        """, (user_id, user_id))
        row = await cursor.fetchone()
        if not row:
            return None
        p = dict(row)
        p["photos_list"] = json.loads(p["photos"]) if p.get("photos") else ([p["photo_id"]] if p.get("photo_id") else [])
        p["distance_str"] = format_place(me, p)
        return p

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
            return bool(await cursor.fetchone())
        return False

async def ban_user(user_id):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("UPDATE users SET is_banned = 1 WHERE user_id = ?", (user_id,))
        await db.commit()
