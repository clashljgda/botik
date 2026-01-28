import sqlite3
import logging
from datetime import datetime, date as date_type
from calendar import monthcalendar, month_name
from aiogram import Bot, Dispatcher, executor, types
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import State, StatesGroup

# ===========================================
# КОНФИГУРАЦИЯ — ЗАМЕНИТЕ НА СВОИ ЗНАЧЕНИЯ!
# ===========================================
BOT_TOKEN = "8576375750:AAFWQyd1fYTHcMOdTJwRp3Sxupd7q16CcN0"      # ← СЮДА ВСТАВЬТЕ ТОКЕН ОТ @BotFather
ADMIN_CHAT_ID = 1154349995         # ← СЮДА ВСТАВЬТЕ ВАШ ЧИСЛОВОЙ chat_id

# ===========================================
# ИНИЦИАЛИЗАЦИЯ
# ===========================================
logging.basicConfig(level=logging.INFO)
bot = Bot(token=BOT_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(bot, storage=storage)

# ===========================================
# FSM СОСТОЯНИЯ
# ===========================================
class BookingStates(StatesGroup):
    choosing_date = State()
    confirming_booking = State()

# ===========================================
# БАЗА ДАННЫХ
# ===========================================
def init_db():
    conn = sqlite3.connect('bookings.db')
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS bookings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL UNIQUE,
            username TEXT,
            date TEXT NOT NULL UNIQUE
        )
    ''')
    conn.commit()
    conn.close()

def get_booked_dates(month: int, year: int):
    conn = sqlite3.connect('bookings.db')
    cursor = conn.cursor()
    cursor.execute(
        "SELECT date FROM bookings WHERE strftime('%m', date) = ? AND strftime('%Y', date) = ?",
        (f"{month:02d}", str(year))
    )
    dates = [row[0] for row in cursor.fetchall()]
    conn.close()
    return dates

def book_training(user_id, username, date):
    try:
        conn = sqlite3.connect('bookings.db')
        cursor = conn.cursor()
        cursor.execute(
            "INSERT OR REPLACE INTO bookings (user_id, username, date) VALUES (?, ?, ?)",
            (user_id, username, date)
        )
        conn.commit()
        conn.close()
        return True
    except:
        return False

def cancel_booking(user_id):
    conn = sqlite3.connect('bookings.db')
    cursor = conn.cursor()
    cursor.execute("SELECT date FROM bookings WHERE user_id = ?", (user_id,))
    result = cursor.fetchone()
    if result:
        date = result[0]
        cursor.execute("DELETE FROM bookings WHERE user_id = ?", (user_id,))
        conn.commit()
        conn.close()
        return date
    conn.close()
    return None

def get_user_booking(user_id):
    conn = sqlite3.connect('bookings.db')
    cursor = conn.cursor()
    cursor.execute("SELECT date FROM bookings WHERE user_id = ?", (user_id,))
    result = cursor.fetchone()
    conn.close()
    return result[0] if result else None

# ===========================================
# КАЛЕНДАРЬ
# ===========================================
def generate_calendar(year, month, booked_dates):
    cal = monthcalendar(year, month)
    today = datetime.now().date()
    keyboard = [[types.InlineKeyboardButton(text=d, callback_data="ignore") for d in ["Пн","Вт","Ср","Чт","Пт","Сб","Вс"]]]
    
    for week in cal:
        row = []
        for day in week:
            if day == 0:
                row.append(types.InlineKeyboardButton(text=" ", callback_data="ignore"))
                continue
            date_str = f"{year}-{month:02d}-{day:02d}"
            date_obj = date_type(year, month, day)
            if date_obj < today:
                text, cb = "—", "ignore"
            elif date_str in booked_dates:
                text, cb = f"❌{day}", "ignore"
            else:
                text = f"✅{day}" if date_obj == today else str(day)
                cb = f"cal_day_{date_str}"
            row.append(types.InlineKeyboardButton(text=text, callback_data=cb))
        keyboard.append(row)
    
    prev_m, prev_y = (month-1, year) if month > 1 else (12, year-1)
    next_m, next_y = (month+1, year) if month < 12 else (1, year+1)
    keyboard.append([
        types.InlineKeyboardButton(text="◀️", callback_data=f"cal_nav_{prev_y}_{prev_m}"),
        types.InlineKeyboardButton(text=f"{month_name[month]} {year}", callback_data="ignore"),
        types.InlineKeyboardButton(text="▶️", callback_data=f"cal_nav_{next_y}_{next_m}"),
    ])
    keyboard.append([types.InlineKeyboardButton(text="↩️ Меню", callback_data="menu")])
    return types.InlineKeyboardMarkup(inline_keyboard=keyboard)

# ===========================================
# ОБРАБОТЧИКИ
# ===========================================
@dp.message_handler(commands=['start'])
async def start(message: types.Message, state: FSMContext):
    await state.finish()
    await message.answer(
        "👋 Привет! Запишитесь на тренировку:",
        reply_markup=types.InlineKeyboardMarkup(inline_keyboard=[
            [types.InlineKeyboardButton(text="📅 Записаться", callback_data="book")],
            [types.InlineKeyboardButton(text="❌ Отменить запись", callback_data="cancel")],
        ])
    )

@dp.callback_query_handler(lambda c: c.data == "menu")
async def menu(callback: types.CallbackQuery, state: FSMContext):
    await state.finish()
    await callback.message.edit_text(
        "Главное меню:",
        reply_markup=types.InlineKeyboardMarkup(inline_keyboard=[
            [types.InlineKeyboardButton(text="📅 Записаться", callback_data="book")],
            [types.InlineKeyboardButton(text="❌ Отменить запись", callback_data="cancel")],
        ])
    )
    await callback.answer()

@dp.callback_query_handler(lambda c: c.data == "book")
async def book(callback: types.CallbackQuery, state: FSMContext):
    now = datetime.now()
    await BookingStates.choosing_date.set()
    await callback.message.edit_text(
        "📅 Выберите дату:",
        reply_markup=generate_calendar(now.year, now.month, get_booked_dates(now.month, now.year))
    )
    await callback.answer()

@dp.callback_query_handler(lambda c: c.data.startswith("cal_nav_"), state=BookingStates.choosing_date)
async def nav(callback: types.CallbackQuery, state: FSMContext):
    _, _, y, m = callback.data.split("_")
    y, m = int(y), int(m)
    await callback.message.edit_text(
        "📅 Выберите дату:",
        reply_markup=generate_calendar(y, m, get_booked_dates(m, y))
    )
    await callback.answer()

@dp.callback_query_handler(lambda c: c.data.startswith("cal_day_"), state=BookingStates.choosing_date)
async def pick_date(callback: types.CallbackQuery, state: FSMContext):
    date_str = callback.data.split("_")[2]
    if datetime.strptime(date_str, "%Y-%m-%d").date() < datetime.now().date():
        await callback.answer("❌ Дата в прошлом!", show_alert=True)
        return
    await state.update_data(date=date_str)
    await BookingStates.confirming_booking.set()
    fmt = datetime.strptime(date_str, "%Y-%m-%d").strftime("%d.%m.%Y")
    await callback.message.edit_text(
        f"✅ Записаться на {fmt}?",
        reply_markup=types.InlineKeyboardMarkup(inline_keyboard=[
            [types.InlineKeyboardButton(text="✅ Да", callback_data=f"confirm_{date_str}")],
            [types.InlineKeyboardButton(text="↩️ Назад", callback_data="book")]
        ])
    )
    await callback.answer()

@dp.callback_query_handler(lambda c: c.data.startswith("confirm_"), state=BookingStates.confirming_booking)
async def confirm(callback: types.CallbackQuery, state: FSMContext):
    date_str = callback.data.split("_")[1]
    user_id = callback.from_user.id
    username = callback.from_user.username or f"id{user_id}"
    
    if not book_training(user_id, username, date_str):
        await callback.message.edit_text(
            "❌ Дата занята. Выберите другую:",
            reply_markup=generate_calendar(
                datetime.now().year,
                datetime.now().month,
                get_booked_dates(datetime.now().month, datetime.now().year)
            )
        )
        return
    
    fmt = datetime.strptime(date_str, "%Y-%m-%d").strftime("%d.%m.%Y")
    try:
        await bot.send_message(ADMIN_CHAT_ID, f"🔔 Новая запись!\n@{username} на {fmt}")
    except Exception as e:
        logging.error(f"Ошибка отправки админу: {e}")
    
    await callback.message.edit_text(
        f"🎉 Записаны на {fmt} в 19:00!\n📍 ул. Спортивная, 15",
        reply_markup=types.InlineKeyboardMarkup(inline_keyboard=[
            [types.InlineKeyboardButton(text="❌ Отменить", callback_data="cancel")],
            [types.InlineKeyboardButton(text="↩️ Меню", callback_data="menu")]
        ])
    )
    await state.finish()
    await callback.answer()

@dp.callback_query_handler(lambda c: c.data == "cancel")
async def cancel(callback: types.CallbackQuery):
    date = cancel_booking(callback.from_user.id)
    if date:
        fmt = datetime.strptime(date, "%Y-%m-%d").strftime("%d.%m.%Y")
        try:
            await bot.send_message(ADMIN_CHAT_ID, f"🔕 Отмена записи @{callback.from_user.username} на {fmt}")
        except:
            pass
        await callback.message.edit_text(
            f"❌ Запись на {fmt} отменена.",
            reply_markup=types.InlineKeyboardMarkup(inline_keyboard=[
                [types.InlineKeyboardButton(text="📅 Записаться", callback_data="book")],
                [types.InlineKeyboardButton(text="↩️ Меню", callback_data="menu")]
            ])
        )
    else:
        await callback.message.edit_text(
            "ℹ️ Нет активных записей.",
            reply_markup=types.InlineKeyboardMarkup(inline_keyboard=[
                [types.InlineKeyboardButton(text="📅 Записаться", callback_data="book")],
                [types.InlineKeyboardButton(text="↩️ Меню", callback_data="menu")]
            ])
        )
    await callback.answer()

@dp.callback_query_handler(lambda c: c.data == "ignore")
async def ignore(callback: types.CallbackQuery):
    await callback.answer()

# ===========================================
# ЗАПУСК
# ===========================================
if __name__ == '__main__':
    init_db()
    print("✅ Бот запущен! (aiogram 2.x)")
    print(f"ℹ️  Токен: {'*' * (len(BOT_TOKEN)-4) + BOT_TOKEN[-4:] if BOT_TOKEN != 'YOUR_BOT_TOKEN' else 'НЕ УСТАНОВЛЕН'}")
    print(f"ℹ️  Админ: {ADMIN_CHAT_ID}")
    executor.start_polling(dp, skip_updates=True)
