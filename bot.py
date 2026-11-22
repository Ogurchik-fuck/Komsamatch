import os
import asyncio
from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
import database as db

TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = 123456789  # <-- ЗАМЕНИ НА СВОЙ ID ИЗ @userinfobot

bot = Bot(token=TOKEN)
dp = Dispatcher()

class Form(StatesGroup):
    name = State()
    age = State()
    gender = State()
    target_gender = State()
    district = State()
    bio = State()
    photo = State()

# Клавиатуры
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
district_kb = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="Центральный округ")],
        [KeyboardButton(text="Ленинский округ (Дзёмги)")],
        [KeyboardButton(text="Другой район")]
    ],
    resize_keyboard=True, one_time_keyboard=True
)

@dp.message(CommandStart())
async def cmd_start(message: types.Message, state: FSMContext):
    await state.clear()
    if not message.from_user.username:
        await message.answer("Для работы бота установи @username в настройках Telegram, иначе с тобой не смогут связаться при мэтче.")
        return

    user = await db.get_user(message.from_user.id)
    if user:
        if user[9]:
            await message.answer("Твоя анкета заблокирована за нарушение правил.")
            return
        await message.answer("С возвращением в КомсаМэтч! Выбери действие в меню ниже:", reply_markup=main_menu_kb)
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
    if not message.text.isdigit() or not (16 <= int(message.text) <= 99):
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
    await message.answer("Из какого ты района?", reply_markup=district_kb)
    await state.set_state(Form.district)

@dp.message(Form.district, F.text.in_(["Центральный округ", "Ленинский округ (Дзёмги)", "Другой район"]))
async def process_district(message: types.Message, state: FSMContext):
    await state.update_data(district=message.text)
    await message.answer("Напиши пару слов о себе (интересы, цель знакомства):", reply_markup=types.ReplyKeyboardRemove())
    await state.set_state(Form.bio)

@dp.message(Form.bio)
async def process_bio(message: types.Message, state: FSMContext):
    await state.update_data(bio=message.text)
    await message.answer("Отправь своё фото для анкеты:")
    await state.set_state(Form.photo)

@dp.message(Form.photo, F.photo)
async def process_photo(message: types.Message, state: FSMContext):
    data = await state.get_data()
    photo_id = message.photo[-1].file_id

    await db.add_user(
        user_id=message.from_user.id,
        username=message.from_user.username,
        name=data["name"],
        age=data["age"],
        gender=data["gender"],
        target_gender=data["target_gender"],
        district=data["district"],
        bio=data["bio"],
        photo_id=photo_id
    )
    await state.clear()
    await message.answer("Анкета готова! Используй кнопки меню ниже:", reply_markup=main_menu_kb)
    await show_next_profile(message, message.from_user.id)

@dp.message(F.text == "🚀 Смотреть анкеты")
async def menu_search(message: types.Message):
    user = await db.get_user(message.from_user.id)
    if not user:
        await message.answer("Сначала заполни анкету через /start")
        return
    if user[9]:
        await message.answer("Твоя анкета заблокирована.")
        return
    await show_next_profile(message, message.from_user.id)

@dp.message(F.text == "👤 Моя анкета")
async def menu_my_profile(message: types.Message):
    user = await db.get_user(message.from_user.id)
    if not user:
        await message.answer("У тебя ещё нет анкеты. Нажми /start")
        return

    _, _, name, age, _, _, district, bio, photo_id, _ = user
    kb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="✏️ Заполнить заново", callback_data="edit_profile")
    ]])
    caption = f"<b>Твоя анкета:</b>\n\n<b>{name}, {age}</b> • {district}\n{bio}"
    await message.answer_photo(photo=photo_id, caption=caption, parse_mode="HTML", reply_markup=kb)

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

    target_id, name, age, district, bio, photo_id = profile
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="❤️ Лайк", callback_data=f"like_{target_id}"),
            InlineKeyboardButton(text="👎 Дальше", callback_data=f"pass_{target_id}")
        ],
        [
            InlineKeyboardButton(text="⚠️ Пожаловаться", callback_data=f"report_{target_id}")
        ]
    ])
    caption = f"<b>{name}, {age}</b> • {district}\n{bio}"
    await message.answer_photo(photo=photo_id, caption=caption, parse_mode="HTML", reply_markup=kb)

@dp.callback_query(F.data.startswith(("like_", "pass_")))
async def handle_vote(callback: types.CallbackQuery):
    action, target_id_str = callback.data.split("_")
    target_id = int(target_id_str)
    user_id = callback.from_user.id
    is_like = (action == "like")

    await callback.message.edit_reply_markup(reply_markup=None)
    is_match = await db.add_like(user_id, target_id, is_like)

    if is_match:
        user_info = await db.get_user(user_id)
        target_info = await db.get_user(target_id)
        if user_info and target_info:
            await callback.message.answer(f"🎉 У вас взаимная симпатия с {target_info[2]}! Написать: @{target_info[1]}")
            await bot.send_message(target_id, f"🎉 У вас взаимная симпатия с {user_info[2]}! Написать: @{user_info[1]}")

    await show_next_profile(callback.message, user_id)
    await callback.answer()

@dp.callback_query(F.data.startswith("report_"))
async def handle_report(callback: types.CallbackQuery):
    target_id = int(callback.data.split("_")[1])
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
            f"Нарушитель: {target_info[2]}, {target_info[3]} (@{target_info[1]}, ID: <code>{target_id}</code>)\n"
            f"Район: {target_info[6]}\n"
            f"Описание: {target_info[7]}"
        )
        await bot.send_photo(ADMIN_ID, photo=target_info[8], caption=caption, parse_mode="HTML", reply_markup=ban_kb)

    await show_next_profile(callback.message, user_id)

@dp.callback_query(F.data.startswith("ban_"))
async def handle_ban(callback: types.CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        return
    target_id = int(callback.data.split("_")[1])
    await db.ban_user(target_id)
    await callback.message.edit_reply_markup(reply_markup=None)
    await callback.message.reply(f"✅ Пользователь <code>{target_id}</code> заблокирован и скрыт из поиска.", parse_mode="HTML")
    await callback.answer()

async def main():
    await db.init_db()
    print("Бот запущен!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
