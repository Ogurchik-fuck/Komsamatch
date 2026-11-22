import os
import asyncio
from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
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
    photo = State()

class UpdateGeo(StatesGroup):
    waiting_geo = State()

class DirectMsg(StatesGroup):
    waiting_content = State()

main_menu_kb = ReplyKeyboardMarkup(
    keyboard=[[KeyboardButton(text="🚀 Смотреть анкеты"), KeyboardButton(text="👤 Моя анкета")]],
    resize_keyboard=True
)
gender_kb = ReplyKeyboardMarkup(
    keyboard=[[KeyboardButton(text="Парень"), KeyboardButton(text="Девушка")]],
    resize_keyboard=True, one_time_keyboard=True
)
target_kb = ReplyKeyboardMarkup(
    keyboard=[[KeyboardButton(text="Девушек"), KeyboardButton(text="Парней")]],
    resize_keyboard=True, one_time_keyboard=True
)
geo_kb = ReplyKeyboardMarkup(
    keyboard=[[KeyboardButton(text="📍 Отправить геопозицию", request_location=True)]],
    resize_keyboard=True, one_time_keyboard=True
)
cancel_kb = ReplyKeyboardMarkup(
    keyboard=[[KeyboardButton(text="❌ Отмена")]],
    resize_keyboard=True
)

@dp.message(CommandStart())
async def cmd_start(message: types.Message, state: FSMContext):
    await state.clear()
    if not message.from_user.username:
        await message.answer("Для работы бота установи @username в настройках Telegram, иначе с тобой не смогут связаться при мэтче.")
        return

    user = await db.get_user(message.from_user.id)
    if user:
        if user.get("is_banned"):
            await message.answer("Твоя анкета заблокирована за нарушение правил.")
            return
        await message.answer(
            f"С возвращением, <b>{user['name']}</b>! Твой профиль активен.\nВыбери действие в меню ниже:",
            parse_mode="HTML",
            reply_markup=main_menu_kb
        )
    else:
        await start_registration(message, state)

async def start_registration(message: types.Message, state: FSMContext):
    await message.answer(
        "Давай создадим анкету для знакомств в Комсомольске-на-Амуре.\n\nКак тебя зовут?",
        reply_markup=types.ReplyKeyboardRemove()
    )
    await state.set_state(Form.name)

@dp.message(Form.name)
async def process_name(message: types.Message, state: FSMContext):
    await state.update_data(name=message.text)
    await message.answer("Сколько тебе лет?")
    await state.set_state(Form.age)

@dp.message(Form.age)
async def process_age(message: types.Message, state: FSMContext):
    if not message.text or not message.text.isdigit() or not (16 <= int(message.text) <= 99):
        await message.answer("Пожалуйста, введи возраст числом (от 16 до 99).")
        return
    await state.update_data(age=int(message.text))
    await message.answer("Твой пол:", reply_markup=gender_kb)
    await state.set_state(Form.gender)

@dp.message(Form.gender, F.text.in_(["Парень", "Девушка"]))
async def process_gender(message: types.Message, state: FSMContext):
    await state.update_data(gender=message.text)
    await message.answer("Кого ты ищешь?", reply_markup=target_kb)
    await state.set_state(Form.target_gender)

@dp.message(Form.target_gender, F.text.in_(["Девушек", "Парней"]))
async def process_target(message: types.Message, state: FSMContext):
    target = "Девушка" if message.text == "Девушек" else "Парень"
    await state.update_data(target_gender=target)
    await message.answer(
        "Нажми кнопку ниже, чтобы отправить свою геопозицию — бот будет показывать расстояние до людей в километрах:",
        reply_markup=geo_kb
    )
    await state.set_state(Form.location)

@dp.message(Form.location, F.location)
async def process_location(message: types.Message, state: FSMContext):
    await state.update_data(lat=message.location.latitude, lon=message.location.longitude)
    await message.answer("Напиши пару слов о себе (интересы, цель знакомства):", reply_markup=types.ReplyKeyboardRemove())
    await state.set_state(Form.bio)

@dp.message(Form.location)
async def process_location_invalid(message: types.Message):
    await message.answer("Пожалуйста, нажми на кнопку «📍 Отправить геопозицию» ниже (не забудь включить GPS на телефоне).", reply_markup=geo_kb)

@dp.message(Form.bio)
async def process_bio(message: types.Message, state: FSMContext):
    await state.update_data(bio=message.text)
    await message.answer("Отправь своё фото для анкеты:")
    await state.set_state(Form.photo)

@dp.message(Form.photo, F.photo)
async def process_photo(message: types.Message, state: FSMContext):
    data = await state.get_data()
    best_photo = max(message.photo, key=lambda p: p.file_size or 0)

    await db.add_user(
        user_id=message.from_user.id,
        username=message.from_user.username,
        name=data["name"],
        age=data["age"],
        gender=data["gender"],
        target_gender=data["target_gender"],
        lat=data["lat"],
        lon=data["lon"],
        bio=data["bio"],
        photo_id=best_photo.file_id
    )
    await state.clear()
    await message.answer("Анкета готова и привязана к твоему аккаунту!", reply_markup=main_menu_kb)
    await show_next_profile(message, message.from_user.id)
@dp.message(F.text.contains("Смотреть анкеты"))
async def menu_search(message: types.Message, state: FSMContext):
    await state.clear()
    user = await db.get_user(message.from_user.id)
    if not user:
        await message.answer("Сначала заполни анкету через /start")
        return
    if user.get("is_banned"):
        await message.answer("Твоя анкета заблокирована.")
        return
    await show_next_profile(message, message.from_user.id)

@dp.message(F.text.contains("Моя анкета"))
async def menu_my_profile(message: types.Message, state: FSMContext):
    await state.clear()
    user = await db.get_user(message.from_user.id)
    if not user:
        await message.answer("У тебя ещё нет анкеты. Нажми /start")
        return

    geo_status = "геопозиция привязана ✅" if user.get("lat") else "геопозиция не указана ⚠️"
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📍 Обновить геопозицию", callback_data="update_geo")],
        [InlineKeyboardButton(text="✏️ Заполнить заново", callback_data="edit_profile")]
    ])
    caption = f"<b>Твоя анкета</b> ({geo_status}):\n\n<b>{user['name']}, {user['age']}</b>\n{user['bio']}"
    await message.answer_photo(photo=user["photo_id"], caption=caption, parse_mode="HTML", reply_markup=kb)

@dp.callback_query(F.data == "update_geo")
async def handle_update_geo(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.answer("Отправь новую геопозицию кнопкой ниже:", reply_markup=geo_kb)
    await state.set_state(UpdateGeo.waiting_geo)
    await callback.answer()

@dp.message(UpdateGeo.waiting_geo, F.location)
async def save_updated_geo(message: types.Message, state: FSMContext):
    await db.update_location(message.from_user.id, message.location.latitude, message.location.longitude)
    await state.clear()
    await message.answer("Геопозиция обновлена!", reply_markup=main_menu_kb)

@dp.callback_query(F.data == "edit_profile")
async def handle_edit_profile(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.edit_reply_markup(reply_markup=None)
    await start_registration(callback.message, state)
    await callback.answer()

async def show_next_profile(message: types.Message, user_id: int):
    profile = await db.get_next_profile(user_id)
    if not profile:
        await message.answer("Анкеты пока закончились. Загляни позже!", reply_markup=main_menu_kb)
        return

    target_id = profile["user_id"]
    dist_text = f" • {profile['distance_str']}" if profile.get("distance_str") else ""
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="❤️ Лайк", callback_data=f"like_{target_id}"),
            InlineKeyboardButton(text="👎 Дальше", callback_data=f"pass_{target_id}")
        ],
        [
            InlineKeyboardButton(text="💌 Написать / Кружочек", callback_data=f"msg_{target_id}"),
            InlineKeyboardButton(text="⚠️ Жалоба", callback_data=f"report_{target_id}")
        ]
    ])
    caption = f"<b>{profile['name']}, {profile['age']}</b>{dist_text}\n{profile['bio']}"
    await message.answer_photo(photo=profile["photo_id"], caption=caption, parse_mode="HTML", reply_markup=kb)

@dp.callback_query(F.data.startswith(("like_", "pass_")))
async def handle_vote(callback: types.CallbackQuery):
    action, target_id_str = callback.data.split("_", 1)
    target_id = int(target_id_str)
    user_id = callback.from_user.id
    is_like = (action == "like")

    await callback.message.edit_reply_markup(reply_markup=None)
    is_match = await db.add_like(user_id, target_id, is_like)

    if is_match:
        user_info = await db.get_user(user_id)
        target_info = await db.get_user(target_id)
        if user_info and target_info:
            kb_to_target = InlineKeyboardMarkup(inline_keyboard=[[
                InlineKeyboardButton(text="💌 Отправить кружочек / сообщение", callback_data=f"msg_{target_id}")
            ]])
            kb_to_user = InlineKeyboardMarkup(inline_keyboard=[[
                InlineKeyboardButton(text="💌 Отправить кружочек / сообщение", callback_data=f"msg_{user_id}")
            ]])
            await callback.message.answer(
                f"🎉 Взаимная симпатия с <b>{target_info['name']}</b>! Написать напрямую: @{target_info['username']}",
                parse_mode="HTML", reply_markup=kb_to_target
            )
            await bot.send_message(
                target_id,
                f"🎉 Взаимная симпатия с <b>{user_info['name']}</b>! Написать напрямую: @{user_info['username']}",
                parse_mode="HTML", reply_markup=kb_to_user
            )

    await show_next_profile(callback.message, user_id)
    await callback.answer()

@dp.callback_query(F.data.startswith("msg_"))
async def start_direct_msg(callback: types.CallbackQuery, state: FSMContext):
    _, target_id_str = callback.data.split("_", 1)
    target_id = int(target_id_str)
    target_info = await db.get_user(target_id)
    if not target_info:
        await callback.answer("Пользователь не найден.", show_alert=True)
        return

    await state.update_data(target_id=target_id)
    await state.set_state(DirectMsg.waiting_content)
    await callback.message.answer(
        f"Отправь текст, <b>видеокружочек</b>, <b>голосовое</b> или фото для <b>{target_info['name']}</b>:",
        parse_mode="HTML",
        reply_markup=cancel_kb
    )
    await callback.answer()

@dp.message(DirectMsg.waiting_content, F.text == "❌ Отмена")
async def cancel_direct_msg(message: types.Message, state: FSMContext):
    await state.clear()
    await message.answer("Отправка отменена.", reply_markup=main_menu_kb)

@dp.message(DirectMsg.waiting_content)
async def send_direct_msg(message: types.Message, state: FSMContext):
    data = await state.get_data()
    target_id = data.get("target_id")
    sender = await db.get_user(message.from_user.id)

    if not target_id or not sender:
        await state.clear()
        await message.answer("Ошибка отправки.", reply_markup=main_menu_kb)
        return

    reply_kb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="↩️ Ответить", callback_data=f"msg_{message.from_user.id}")
    ]])
    header = f"💌 Сообщение от <b>{sender['name']}, {sender['age']}</b> (@{sender['username']}):"

    try:
        await bot.send_message(target_id, header, parse_mode="HTML")
        await message.copy_to(chat_id=target_id, reply_markup=reply_kb)
        await message.answer("Доставлено! ✅", reply_markup=main_menu_kb)
    except Exception:
        await message.answer("Не удалось доставить сообщение (пользователь заблокировал бота).", reply_markup=main_menu_kb)

    await state.clear()

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
        ban_kb = InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text="🚫 Забанить анкету", callback_data=f"ban_{target_id}")
        ]])
        caption = (
            f"🚨 <b>Новая жалоба!</b>\n"
            f"Нарушитель: {target_info['name']}, {target_info['age']} (@{target_info['username']}, ID: <code>{target_id}</code>)\n"
            f"Описание: {target_info['bio']}"
        )
        await bot.send_photo(ADMIN_ID, photo=target_info["photo_id"], caption=caption, parse_mode="HTML", reply_markup=ban_kb)

    await show_next_profile(callback.message, user_id)

@dp.callback_query(F.data.startswith("ban_"))
async def handle_ban(callback: types.CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        return
    _, target_id_str = callback.data.split("_", 1)
    target_id = int(target_id_str)
    await db.ban_user(target_id)
    await callback.message.edit_reply_markup(reply_markup=None)
    await callback.message.reply(f"✅ Пользователь <code>{target_id}</code> заблокирован и скрыт из поиска.", parse_mode="HTML")
    await callback.answer()

async def main():
    await db.init_db()
    await bot.delete_webhook(drop_pending_updates=True)
    print("Бот запущен!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
