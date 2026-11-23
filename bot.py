import os
import asyncio
from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (
    ReplyKeyboardMarkup, KeyboardButton,
    InlineKeyboardMarkup, InlineKeyboardButton,
    InputMediaPhoto, InputMediaVideo
)
import database as db

TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = 9131132339

bot = Bot(token=TOKEN)
dp = Dispatcher()

class Form(StatesGroup):
    name = State()
    age = State()
    gender = State()
    target_gender = State()
    location = State()
    bio = State()
    photos = State()
    video = State()

class UpdateGeo(StatesGroup):
    waiting_geo = State()

class UpdateBio(StatesGroup):
    waiting_bio = State()

main_menu_kb = ReplyKeyboardMarkup(
    keyboard=[[KeyboardButton(text="🔥 Смотреть анкеты"), KeyboardButton(text="👤 Моя анкета")]],
    resize_keyboard=True
)
gender_kb = ReplyKeyboardMarkup(
    keyboard=[[KeyboardButton(text="🙋‍♂️ Парень"), KeyboardButton(text="🙋‍♀️ Девушка")]],
    resize_keyboard=True, one_time_keyboard=True
)
target_kb = ReplyKeyboardMarkup(
    keyboard=[[KeyboardButton(text="💃 Девушек"), KeyboardButton(text="🕺 Парней")]],
    resize_keyboard=True, one_time_keyboard=True
)

DISTRICTS = [
    "Центральный округ",
    "Дзёмги (Ленинский округ)",
    "Привокзальный район",
    "66-й квартал / Мылки",
    "Таёжный / Дружба",
    "Менделеева / Амурлитмаш",
    "Парус / Силинский",
    "Хапсоль / Индустриальный"
]

geo_kb = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="📍 Поделиться геопозицией (покажет км)", request_location=True)],
        [KeyboardButton(text="🕶 Инкогнито (просто г. Комсомольск-на-Амуре)")],
        [KeyboardButton(text="Центральный округ"), KeyboardButton(text="Дзёмги (Ленинский округ)")],
        [KeyboardButton(text="Привокзальный район"), KeyboardButton(text="66-й квартал / Мылки")],
        [KeyboardButton(text="Таёжный / Дружба"), KeyboardButton(text="Менделеева / Амурлитмаш")],
        [KeyboardButton(text="Парус / Силинский"), KeyboardButton(text="Хапсоль / Индустриальный")]
    ],
    resize_keyboard=True, one_time_keyboard=True
)
photos_done_kb = ReplyKeyboardMarkup(
    keyboard=[[KeyboardButton(text="✅ Хватит фото, идём дальше")]],
    resize_keyboard=True
)
skip_video_kb = ReplyKeyboardMarkup(
    keyboard=[[KeyboardButton(text="⏭ Пропустить видео")]],
    resize_keyboard=True, one_time_keyboard=True
)
cancel_kb = ReplyKeyboardMarkup(
    keyboard=[[KeyboardButton(text="❌ Отмена")]],
    resize_keyboard=True
)

def make_quick_kb(old_value, allow_skip=False):
    buttons = []
    if old_value:
        buttons.append([KeyboardButton(text=str(old_value))])
    if allow_skip:
        buttons.append([KeyboardButton(text="⏭ Пропустить")])
    if not buttons:
        return types.ReplyKeyboardRemove()
    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True, one_time_keyboard=True)

def format_profile_card(user: dict, is_own=False, prefix="") -> str:
    header = "✨ <b>Твоя визитка в КомсаМэтч</b>\n" if is_own else prefix
    place = user.get("location_text") or "г. Комсомольск-на-Амуре"
    dist = f"📍 <i>{user['distance_str']}</i>\n" if user.get("distance_str") else f"📍 <i>{place}</i>\n"
    bio_block = f"<blockquote>{user['bio']}</blockquote>" if user.get("bio") and user["bio"].strip() else ""
    return f"{header}👤 <b>{user['name']}, {user['age']}</b>\n{dist}{bio_block}"

async def send_full_profile(chat_id: int, user: dict, reply_markup=None, is_own=False, prefix=""):
    photos = user.get("photos_list", [])
    caption = format_profile_card(user, is_own=is_own, prefix=prefix)
    video_id = user.get("video_id")
    video_type = user.get("video_type")

    media = []
    for idx, p in enumerate(photos):
        if idx == 0:
            media.append(InputMediaPhoto(media=p, caption=caption, parse_mode="HTML"))
        else:
            media.append(InputMediaPhoto(media=p))

    if video_id and video_type == "video":
        if not media:
            media.append(InputMediaVideo(media=video_id, caption=caption, parse_mode="HTML"))
        else:
            media.append(InputMediaVideo(media=video_id))

    if len(media) > 1:
        await bot.send_media_group(chat_id=chat_id, media=media)
        if video_id and video_type == "video_note":
            await bot.send_video_note(chat_id=chat_id, video_note=video_id, reply_markup=reply_markup)
        elif reply_markup:
            await bot.send_message(chat_id=chat_id, text="👇 <b>Выбери действие:</b>", parse_mode="HTML", reply_markup=reply_markup)
    else:
        photo_id = next(iter(photos), None) or user.get("photo_id")
        if video_id and video_type == "video_note":
            await bot.send_photo(chat_id=chat_id, photo=photo_id, caption=caption, parse_mode="HTML")
            await bot.send_video_note(chat_id=chat_id, video_note=video_id, reply_markup=reply_markup)
        elif video_id and video_type == "video":
            await bot.send_video(chat_id=chat_id, video=video_id, caption=caption, parse_mode="HTML", reply_markup=reply_markup)
        else:
            await bot.send_photo(chat_id=chat_id, photo=photo_id, caption=caption, parse_mode="HTML", reply_markup=reply_markup)
@dp.message(CommandStart())
async def cmd_start(message: types.Message, state: FSMContext):
    await state.clear()
    if not message.from_user.username:
        await message.answer("👋 Привет! Сначала задай <b>@username</b> в настройках Telegram — так твои пары смогут написать тебе при мэтче!", parse_mode="HTML")
        return
    user = await db.get_user(message.from_user.id)
    if user:
        if user.get("is_banned"):
            await message.answer("🚫 Твоя анкета заблокирована.")
            return
        if not user.get("is_active", 1):
            kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🔥 Вернуть анкету в поиск", callback_data="wake_up")]])
            await message.answer(f"💫 <b>Мы тебя помним, {user['name']}!</b>\nТвоя анкета сейчас спит. Хочешь снова пообщаться с кем-то новым?", parse_mode="HTML", reply_markup=kb)
            return
        await message.answer(f"👋 С возвращением, <b>{user['name']}</b>! Твой профиль активен.\nЖми на кнопки ниже 👇", parse_mode="HTML", reply_markup=main_menu_kb)
    else:
        await message.answer("🌊 <b>Добро пожаловать в КомсаМэтч!</b>\nДавай соберём твою анкету за 1 минуту!", parse_mode="HTML")
        await start_registration(message, state)

async def start_registration(message: types.Message, state: FSMContext, old_user: dict = None):
    await state.update_data(old_user=old_user or {}, photos_list=[])
    await message.answer("✏️ <b>Шаг 1/7.</b> Как тебя зовут?", parse_mode="HTML", reply_markup=make_quick_kb((old_user or {}).get("name")))
    await state.set_state(Form.name)

@dp.message(Form.name)
async def process_name(message: types.Message, state: FSMContext):
    data = await state.get_data()
    await state.update_data(name=message.text)
    await message.answer("🎂 <b>Шаг 2/7.</b> Сколько тебе лет?", parse_mode="HTML", reply_markup=make_quick_kb(data.get("old_user", {}).get("age")))
    await state.set_state(Form.age)

@dp.message(Form.age)
async def process_age(message: types.Message, state: FSMContext):
    if not message.text or not message.text.isdigit():
        await message.answer("⚠️ Введи свой возраст цифрами:")
        return
    age = int(message.text)
    if age < 14:
        await message.answer("🛡 К сожалению, нашим ботом можно пользоваться с <b>14 лет</b> в связи с заботой о вас и вашей безопасности.", parse_mode="HTML")
        return
    if age > 67:
        await message.answer("⚠️ Просим указать ваш настоящий возраст (от 14 до 67 лет):")
        return
    await state.update_data(age=age)
    await message.answer("👤 <b>Шаг 3/7.</b> Выбери свой пол:", parse_mode="HTML", reply_markup=gender_kb)
    await state.set_state(Form.gender)

@dp.message(Form.gender)
async def process_gender(message: types.Message, state: FSMContext):
    if "Парень" in message.text:
        gender = "Парень"
    elif "Девушка" in message.text:
        gender = "Девушка"
    else:
        await message.answer("Выбери вариант кнопкой ниже 👇", reply_markup=gender_kb)
        return
    await state.update_data(gender=gender)
    await message.answer("💘 <b>Шаг 4/7.</b> Кого ты хочешь найти?", parse_mode="HTML", reply_markup=target_kb)
    await state.set_state(Form.target_gender)

@dp.message(Form.target_gender)
async def process_target(message: types.Message, state: FSMContext):
    if "Девушек" in message.text:
        target = "Девушка"
    elif "Парней" in message.text:
        target = "Парень"
    else:
        await message.answer("Выбери вариант кнопкой ниже 👇", reply_markup=target_kb)
        return
    await state.update_data(target_gender=target)
    await message.answer(
        "📍 <b>Шаг 5/7.</b> Отправь геопозицию (чтобы видеть км до людей), выбери свой район Комсомольска-на-Амуре или останься инкогнито 👇",
        parse_mode="HTML", reply_markup=geo_kb
    )
    await state.set_state(Form.location)

@dp.message(Form.location, F.location)
async def process_location_gps(message: types.Message, state: FSMContext):
    data = await state.get_data()
    await state.update_data(lat=message.location.latitude, lon=message.location.longitude, location_text="г. Комсомольск-на-Амуре")
    await ask_bio(message, state, data)

@dp.message(Form.location)
async def process_location_text(message: types.Message, state: FSMContext):
    data = await state.get_data()
    text = (message.text or "").strip()
    if "Инкогнито" in text or not text:
        loc_text = "г. Комсомольск-на-Амуре"
    elif text in DISTRICTS:
        loc_text = f"р-н {text}"
    else:
        loc_text = text[:40]
    await state.update_data(lat=None, lon=None, location_text=loc_text)
    await ask_bio(message, state, data)

async def ask_bio(message: types.Message, state: FSMContext, data: dict):
    old_bio = data.get("old_user", {}).get("bio")
    await message.answer(
        "📝 <b>Шаг 6/7.</b> Напиши пару слов о себе (интересы, кого ищешь) или нажми <b>«⏭ Пропустить»</b> — анкету можно создать и без текста:",
        parse_mode="HTML", reply_markup=make_quick_kb(old_bio, allow_skip=True)
    )
    await state.set_state(Form.bio)

@dp.message(Form.bio)
async def process_bio(message: types.Message, state: FSMContext):
    bio = "" if (message.text and "Пропустить" in message.text) else (message.text or "")
    await state.update_data(bio=bio)
    await message.answer("📸 <b>Шаг 7/7.</b> Загрузи от <b>1 до 3 фото</b> для анкеты:", parse_mode="HTML", reply_markup=types.ReplyKeyboardRemove())
    await state.set_state(Form.photos)

@dp.message(Form.photos, F.photo)
async def process_photos(message: types.Message, state: FSMContext):
    data = await state.get_data()
    photos = data.get("photos_list", [])
    best_photo = max(message.photo, key=lambda p: p.file_size or 0)
    photos.append(best_photo.file_id)
    await state.update_data(photos_list=photos)
    if len(photos) < 3:
        await message.answer(f"✅ Фото {len(photos)} из 3 добавлено! Кидай ещё или жми кнопку 👇", reply_markup=photos_done_kb)
    else:
        await ask_for_video(message, state)

@dp.message(Form.photos, F.text.contains("Хватит фото"))
async def finish_photos(message: types.Message, state: FSMContext):
    data = await state.get_data()
    if not data.get("photos_list"):
        await message.answer("Сначала отправь хотя бы 1 фото 📸")
        return
    await ask_for_video(message, state)

async def ask_for_video(message: types.Message, state: FSMContext):
    await message.answer("🎬 <b>Финальный штрих!</b> Запиши <b>видеокружочек</b> или отправь короткое <b>видео</b> (или нажми «Пропустить видео») 👇", parse_mode="HTML", reply_markup=skip_video_kb)
    await state.set_state(Form.video)

@dp.message(Form.video, F.video_note | F.video)
async def process_video(message: types.Message, state: FSMContext):
    if message.video_note:
        await state.update_data(video_id=message.video_note.file_id, video_type="video_note")
    else:
        await state.update_data(video_id=message.video.file_id, video_type="video")
    await complete_registration(message, state)

@dp.message(Form.video, F.text.contains("Пропустить видео"))
async def skip_video(message: types.Message, state: FSMContext):
    await state.update_data(video_id=None, video_type=None)
    await complete_registration(message, state)

async def complete_registration(message: types.Message, state: FSMContext):
    data = await state.get_data()
    await db.add_user(
        user_id=message.from_user.id, username=message.from_user.username,
        name=data["name"], age=data["age"], gender=data["gender"],
        target_gender=data["target_gender"], lat=data.get("lat"), lon=data.get("lon"),
        location_text=data.get("location_text", "г. Комсомольск-на-Амуре"),
        bio=data.get("bio", ""), photos_list=data["photos_list"],
        video_id=data.get("video_id"), video_type=data.get("video_type")
    )
    await state.clear()
    await message.answer("🎉 <b>Готово!</b> Твоя анкета опубликована. Вот как её видят другие 👇", parse_mode="HTML", reply_markup=main_menu_kb)
    await menu_my_profile(message, state)
@dp.message(F.text.contains("Смотреть анкеты"))
async def menu_search(message: types.Message, state: FSMContext):
    await state.clear()
    user = await db.get_user(message.from_user.id)
    if not user:
        await message.answer("Сначала создай анкету через /start")
        return
    if user.get("is_banned"):
        await message.answer("🚫 Твоя анкета заблокирована.")
        return
    if not user.get("is_active", 1):
        kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🔥 Вернуть анкету в поиск", callback_data="wake_up")]])
        await message.answer(f"💫 <b>Мы тебя помним, {user['name']}!</b>\nВключи анкету обратно, чтобы смотреть других!", parse_mode="HTML", reply_markup=kb)
        return
    await show_next_profile(message.chat.id, message.from_user.id)

@dp.message(F.text.contains("Моя анкета"))
async def menu_my_profile(message: types.Message, state: FSMContext):
    await state.clear()
    user = await db.get_user(message.from_user.id)
    if not user:
        await message.answer("У тебя ещё нет анкеты. Нажми /start")
        return
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✏️ Заполнить заново (быстро)", callback_data="edit_profile")],
        [InlineKeyboardButton(text="📝 Изменить текст о себе", callback_data="add_bio_btn")],
        [InlineKeyboardButton(text="📍 Сменить геопозицию / район", callback_data="update_geo")],
        [InlineKeyboardButton(text="💤 Скрыть анкету (удалить из поиска)", callback_data="sleep_profile")]
    ])
    await send_full_profile(message.chat.id, user, reply_markup=kb, is_own=True)

@dp.callback_query(F.data == "sleep_profile")
async def handle_sleep_profile(callback: types.CallbackQuery):
    await db.set_active(callback.from_user.id, False)
    await callback.message.edit_reply_markup(reply_markup=None)
    await callback.message.answer("💤 <b>Анкета скрыта!</b> Мы сохранили твои данные. Чтобы вернуться — нажми /start.", parse_mode="HTML", reply_markup=types.ReplyKeyboardRemove())
    await callback.answer()

@dp.callback_query(F.data == "wake_up")
async def handle_wake_up(callback: types.CallbackQuery):
    await db.set_active(callback.from_user.id, True)
    await callback.message.edit_reply_markup(reply_markup=None)
    await callback.message.answer("🔥 <b>С возвращением в игру!</b> Анкета снова в поиске.", parse_mode="HTML", reply_markup=main_menu_kb)
    await show_next_profile(callback.message.chat.id, callback.from_user.id)
    await callback.answer()

@dp.callback_query(F.data == "update_geo")
async def handle_update_geo(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.answer("📍 Отправь GPS, выбери район или останься инкогнито 👇", reply_markup=geo_kb)
    await state.set_state(UpdateGeo.waiting_geo)
    await callback.answer()

@dp.message(UpdateGeo.waiting_geo, F.location)
async def save_updated_geo_gps(message: types.Message, state: FSMContext):
    await db.update_location(message.from_user.id, message.location.latitude, message.location.longitude, "г. Комсомольск-на-Амуре")
    await state.clear()
    await message.answer("✅ Геопозиция обновлена!", reply_markup=main_menu_kb)

@dp.message(UpdateGeo.waiting_geo)
async def save_updated_geo_text(message: types.Message, state: FSMContext):
    text = (message.text or "").strip()
    if "Инкогнито" in text or not text:
        loc_text = "г. Комсомольск-на-Амуре"
    elif text in DISTRICTS:
        loc_text = f"р-н {text}"
    else:
        loc_text = text[:40]
    await db.update_location(message.from_user.id, None, None, loc_text)
    await state.clear()
    await message.answer(f"✅ Локация обновлена: <b>{loc_text}</b>!", parse_mode="HTML", reply_markup=main_menu_kb)

@dp.callback_query(F.data == "add_bio_btn")
async def handle_add_bio_prompt(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.answer("📝 Напиши новый текст о себе (или отправь «-», чтобы очистить):", reply_markup=cancel_kb)
    await state.set_state(UpdateBio.waiting_bio)
    await callback.answer()

@dp.message(UpdateBio.waiting_bio, F.text == "❌ Отмена")
async def cancel_bio_update(message: types.Message, state: FSMContext):
    await state.clear()
    await message.answer("Отменено.", reply_markup=main_menu_kb)

@dp.message(UpdateBio.waiting_bio)
async def save_updated_bio(message: types.Message, state: FSMContext):
    new_bio = "" if message.text.strip() == "-" else message.text
    await db.update_bio(message.from_user.id, new_bio)
    await state.clear()
    await message.answer("✅ Текст анкеты обновлён!", reply_markup=main_menu_kb)

@dp.callback_query(F.data == "edit_profile")
async def handle_edit_profile(callback: types.CallbackQuery, state: FSMContext):
    old_user = await db.get_user(callback.from_user.id)
    await callback.message.edit_reply_markup(reply_markup=None)
    await callback.message.answer("⚡ <b>Режим быстрого заполнения:</b> нажимай на кнопки внизу со старыми данными или вводи новые!", parse_mode="HTML")
    await start_registration(callback.message, state, old_user=old_user)
    await callback.answer()

async def show_next_profile(chat_id: int, user_id: int):
    need_bio_prompt = await db.increment_views_and_check_prompt(user_id)
    if need_bio_prompt:
        bio_kb = InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text="✍️ Добавить текст в анкету", callback_data="add_bio_btn")
        ]])
        await bot.send_message(
            chat_id,
            "💡 <b>Маленький совет!</b> Ты посмотрел уже больше 10 анкет, а в твоём профиле пока пусто.\nМожет быть, всё-таки добавим пару слов о себе? Анкеты с описанием получают заметно больше лайков 👇",
            parse_mode="HTML", reply_markup=bio_kb
        )

    admirer = await db.get_incoming_like(user_id)
    if admirer:
        target_id = admirer["user_id"]
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="❤️ Взаимно!", callback_data=f"like_{target_id}"), InlineKeyboardButton(text="👎 Неинтересно", callback_data=f"pass_{target_id}")],
            [InlineKeyboardButton(text="⚠️ Жалоба", callback_data=f"report_{target_id}")]
        ])
        await send_full_profile(chat_id, admirer, reply_markup=kb, prefix="💘 <b>Ты понравился этому человеку!</b>\n")
        return

    profile = await db.get_next_profile(user_id)
    if not profile:
        await bot.send_message(chat_id, "😴 <b>Анкеты пока закончились!</b> Загляни чуть позже!", parse_mode="HTML", reply_markup=main_menu_kb)
        return
    target_id = profile["user_id"]
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❤️ Лайк", callback_data=f"like_{target_id}"), InlineKeyboardButton(text="👎 Дальше", callback_data=f"pass_{target_id}")],
        [InlineKeyboardButton(text="⚠️ Жалоба", callback_data=f"report_{target_id}")]
    ])
    await send_full_profile(chat_id, profile, reply_markup=kb, is_own=False)

@dp.callback_query(F.data == "view_likes")
async def handle_view_likes(callback: types.CallbackQuery):
    await callback.message.edit_reply_markup(reply_markup=None)
    await show_next_profile(callback.message.chat.id, callback.from_user.id)
    await callback.answer()

@dp.callback_query(F.data.startswith(("like_", "pass_")))
async def handle_vote(callback: types.CallbackQuery):
    action, target_id_str = callback.data.split("_", 1)
    target_id = int(target_id_str)
    user_id = callback.from_user.id
    is_like = (action == "like")
    await callback.message.edit_reply_markup(reply_markup=None)
    is_match = await db.add_like(user_id, target_id, is_like)

    if is_match:
        u1 = await db.get_user(user_id)
        u2 = await db.get_user(target_id)
        if u1 and u2:
            next_kb = InlineKeyboardMarkup(inline_keyboard=[[
                InlineKeyboardButton(text="🔥 Смотреть дальше", callback_data="view_likes")
            ]])
            await callback.message.answer(
                f"🎉 <b>Бинго! Взаимная симпатия с <a href='https://t.me{u2['username']}'>{u2['name']}</a>!</b>\nНажимай на имя, чтобы перейти в личку 💌",
                parse_mode="HTML", reply_markup=next_kb
            )
            await bot.send_message(
                target_id,
                f"🎉 <b>Бинго! Взаимная симпатия с <a href='https://t.me{u1['username']}'>{u1['name']}</a>!</b>\nНажимай на имя, чтобы перейти в личку 💌",
                parse_mode="HTML", reply_markup=next_kb
            )
    else:
        if is_like:
            try:
                view_kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="👀 Посмотреть, кто это", callback_data="view_likes")]])
                await bot.send_message(
                    target_id,
                    "💘 <b>Твоя анкета кому-то понравилась!</b>\nЗаканчивай с просмотром и давай посмотрим, кто поставил лайк 👇",
                    parse_mode="HTML", reply_markup=view_kb
                )
            except Exception:
                pass
        await show_next_profile(callback.message.chat.id, user_id)

    await callback.answer()

@dp.callback_query(F.data.startswith("report_"))
async def handle_report(callback: types.CallbackQuery):
    _, target_id_str = callback.data.split("_", 1)
    target_id = int(target_id_str)
    user_id = callback.from_user.id
    await callback.message.edit_reply_markup(reply_markup=None)
    await db.add_like(user_id, target_id, False)
    await callback.answer("Жалоба отправлена модератору.", show_alert=True)
    target_info = await db.get_user(target_id)
    if target_info and ADMIN_ID:
        ban_kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🚫 Забанить анкету", callback_data=f"ban_{target_id}")]])
        caption = f"🚨 <b>Новая жалоба!</b>\nНарушитель: {target_info['name']}, {target_info['age']} (@{target_info['username']}, ID: <code>{target_id}</code>)\nОписание: {target_info['bio']}"
        first_photo = next(iter(target_info.get("photos_list", [])), None)
        if first_photo:
            await bot.send_photo(ADMIN_ID, photo=first_photo, caption=caption, parse_mode="HTML", reply_markup=ban_kb)
        else:
            await bot.send_message(ADMIN_ID, text=caption, parse_mode="HTML", reply_markup=ban_kb)
    await show_next_profile(callback.message.chat.id, user_id)

@dp.callback_query(F.data.startswith("ban_"))
async def handle_ban(callback: types.CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        return
    _, target_id_str = callback.data.split("_", 1)
    target_id = int(target_id_str)
    await db.ban_user(target_id)
    await callback.message.edit_reply_markup(reply_markup=None)
    await callback.message.reply(f"✅ Пользователь <code>{target_id}</code> заблокирован.", parse_mode="HTML")
    await callback.answer()

async def main():
    await db.init_db()
    await bot.delete_webhook(drop_pending_updates=True)
    print("Бот запущен!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
