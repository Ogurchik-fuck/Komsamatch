import asyncio
from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
import database as db

TOKEN = "9262978497:AAESszKNYsZkQ0YRp9X7DWq2YTnKcJaOk10"

bot = Bot(token=TOKEN)
dp = Dispatcher()

class Form(StatesGroup):
    name = State()
    age = State()
    gender = State()
    target_gender = State()
    bio = State()
    photo = State()

gender_kb = ReplyKeyboardMarkup(
    keyboard=[[KeyboardButton(text="Парень"), KeyboardButton(text="Девушка")]],
    resize_keyboard=True, one_time_keyboard=True
)
target_kb = ReplyKeyboardMarkup(
    keyboard=[[KeyboardButton(text="Девушек"), KeyboardButton(text="Парней")]],
    resize_keyboard=True, one_time_keyboard=True
)

@dp.message(CommandStart())
async def cmd_start(message: types.Message, state: FSMContext):
    if not message.from_user.username:
        await message.answer("Для работы бота установи @username в настройках Telegram, иначе с тобой не смогут связаться при мэтче.")
        return
    await message.answer("Привет! Давай создадим анкету для знакомств в Комсомольске-на-Амуре.\n\nКак тебя зовут?")
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
    await message.answer("Напиши пару слов о себе (интересы, район города, цель знакомства):", reply_markup=types.ReplyKeyboardRemove())
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
        bio=data["bio"],
        photo_id=photo_id
    )
    await state.clear()
    await message.answer("Анкета готова! Начинаем поиск...")
    await show_next_profile(message, message.from_user.id)

async def show_next_profile(message: types.Message, user_id: int):
    profile = await db.get_next_profile(user_id)
    if not profile:
        await message.answer("Анкеты пока закончились. Загляни позже!")
        return

    target_id, name, age, bio, photo_id = profile
    kb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="❤️ Лайк", callback_data=f"like_{target_id}"),
        InlineKeyboardButton(text="👎 Дальше", callback_data=f"pass_{target_id}")
    ]])
    caption = f"<b>{name}, {age}</b>\n{bio}"
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
        user_info = await db.get_username(user_id)
        target_info = await db.get_username(target_id)
        await callback.message.answer(f"🎉 У вас взаимная симпатия с {target_info[1]}! Написать: @{target_info[0]}")
        await bot.send_message(target_id, f"🎉 У вас взаимная симпатия с {user_info[1]}! Написать: @{user_info[0]}")

    await show_next_profile(callback.message, user_id)
    await callback.answer()

async def main():
    await db.init_db()
    print("Бот запущен!")
    await bot.delete_webhook(drop_pending_updates=True); await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())