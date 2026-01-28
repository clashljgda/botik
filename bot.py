import asyncio
import sqlite3
from datetime import datetime, date as date_type
from calendar import monthcalendar, month_name
from aiogram import Bot, Dispatcher, Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
import warnings
warnings.filterwarnings("ignore", category=UserWarning, message=".*protected_namespaces.*")  # Подавляем предупреждение pydantic

# ===========================================
# КОНФИГУРАЦИЯ (замените на свои значения!)
# ===========================================
BOT_TOKEN = "8576375750:AAFWQyd1fYTHcMOdTJwRp3Sxupd7q16CcN0"  # ← Вставьте токен от @BotFather
ADMIN_CHAT_ID = 1154349995     # ← Вставьте ваш chat_id (узнать у @userinfobot)

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())
router = Router()
dp.include_router(router)

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

def get_booked_dates(month: int, year: int) -> list[str]:
    conn = sqlite3.connect('bookings.db')
    cursor = conn.cursor()
    cursor.execute(
        "SELECT date FROM bookings WHERE strftime('%m', date) = ? AND strftime('%Y', date) = ?",
        (f"{month:02d}", str(year))
    )
    dates = [row[0] for row in cursor.fetchall()]
    conn.close()
    return dates

def book_training(user_id: int, username: str, date: str) -> bool:
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

def cancel_booking(user_id: int) -> str | None:
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

def get_user_booking(user_id: int) -> str | None:
    conn = sqlite3.connect('bookings.db')
    cursor = conn.cursor()
    cursor.execute("SELECT date FROM bookings WHERE user_id = ?", (user_id,))
    result = cursor.fetchone()
    conn.close()
    return result[0] if result else None

# ===========================================
# КАЛЕНДАРЬ
# ===========================================
def generate_calendar(year: int, month: int, booked_dates: list[str]) -> InlineKeyboardMarkup:
    cal = monthcalendar(year, month)
    today = datetime.now().date()
    keyboard = [[InlineKeyboardButton(text=day, callback_data="ignore") for day in ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]]]
    
    for week in cal:
        row = []
        for day in week:
            if day == 0:
                row.append(InlineKeyboardButton(text=" ", callback_data="ignore"))
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
            row.append(InlineKeyboardButton(text=text, callback_data=cb))
        keyboard.append(row)
    
    prev_m, prev_y = (month-1, year) if month > 1 else (12, year-1)
    next_m, next_y = (month+1, year) if month < 12 else (1, year+1)
    keyboard.append([
        InlineKeyboardButton(text="◀️", callback_data=f"cal_nav_{prev_y}_{prev_m}"),
        InlineKeyboardButton(text=f"{month_name[month]} {year}", callback_data="ignore"),
        InlineKeyboardButton(text="▶️", callback_data=f"cal_nav_{next_y}_{next_m}"),
    ])
    keyboard.append([InlineKeyboardButton(text="↩️ Меню", callback_data="menu")])
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

# ===========================================
# ОБРАБОТЧИКИ
# ===========================================
@router.message(Command("start"))
async def start(message: Message, state: FSMContext):
    await state.clear()
    await message.answer(
        "👋 Добро пожаловать!\nЗапишитесь на тренировку через календарь:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📅 Записаться", callback_data="book")],
            [InlineKeyboardButton(text="❌ Отменить запись", callback_data="cancel")],
        ])
    )

@router.callback_query(F.data == "menu")
async def menu(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text("Главное меню:", reply_markup=InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📅 Записаться", callback_data="book")],
        [InlineKeyboardButton(text="❌ Отменить запись", callback_data="cancel")],
    ]))
    await callback.answer()

@router.callback_query(F.data == "book")
async def book(callback: CallbackQuery, state: FSMContext):
    now = datetime.now()
    await state.set_state(BookingStates.choosing_date)
    await callback.message.edit_text(
        "📅 Выберите дату:",
        reply_markup=generate_calendar(now.year, now.month, get_booked_dates(now.month, now.year))
    )
    await callback.answer()

@router.callback_query(F.data.startswith("cal_nav_"))
async def nav(callback: CallbackQuery, state: FSMContext):
    _, _, y, m = callback.data.split("_")
    y, m = int(y), int(m)
    await callback.message.edit_text(
        "📅 Выберите дату:",
        reply_markup=generate_calendar(y, m, get_booked_dates(m, y))
    )
    await callback.answer()

@router.callback_query(F.data.startswith("cal_day_"))
async def pick_date(callback: CallbackQuery, state: FSMContext):
    date_str = callback.data.split("_")[2]
    if datetime.strptime(date_str, "%Y-%m-%d").date() < datetime.now().date():
        await callback.answer("❌ Дата в прошлом!", show_alert=True)
        return
    await state.update_data(date=date_str)
    await state.set_state(BookingStates.confirming_booking)
    fmt = datetime.strptime(date_str, "%Y-%m-%d").strftime("%d.%m.%Y")
    await callback.message.edit_text(
        f"✅ Записаться на {fmt}?",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="✅ Да", callback_data=f"confirm_{date_str}")],
            [InlineKeyboardButton(text="↩️ Назад", callback_data="book")]
        ])
    )
    await callback.answer()

@router.callback_query(F.data.startswith("confirm_"))
async def confirm(callback: CallbackQuery, state: FSMContext):
    date_str = callback.data.split("_")[1]
    user_id = callback.from_user.id
    username = callback.from_user.username or f"id{user_id}"
    
    if not book_training(user_id, username, date_str):
        await callback.message.edit_text("❌ Дата занята. Выберите другую:", reply_markup=generate_calendar(
            datetime.now().year, datetime.now().month, get_booked_dates(datetime.now().month, datetime.now().year)
        ))
        return
    
    fmt = datetime.strptime(date_str, "%Y-%m-%d").strftime("%d.%m.%Y")
    try:
        await bot.send_message(ADMIN_CHAT_ID, f"🔔 Новая запись!\n@{username} на {fmt}")
    except:
        pass
    
    await callback.message.edit_text(
        f"🎉 Записаны на {fmt} в 19:00!\n📍 ул. Спортивная, 15",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="❌ Отменить", callback_data="cancel")],
            [InlineKeyboardButton(text="↩️ Меню", callback_data="menu")]
        ])
    )
    await state.clear()
    await callback.answer()

@router.callback_query(F.data == "cancel")
async def cancel(callback: CallbackQuery):
    date = cancel_booking(callback.from_user.id)
    if date:
        fmt = datetime.strptime(date, "%Y-%m-%d").strftime("%d.%m.%Y")
        try:
            await bot.send_message(ADMIN_CHAT_ID, f"🔕 Отмена записи @{callback.from_user.username} на {fmt}")
        except:
            pass
        await callback.message.edit_text(f"❌ Запись на {fmt} отменена.", reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📅 Записаться", callback_data="book")],
            [InlineKeyboardButton(text="↩️ Меню", callback_data="menu")]
        ]))
    else:
        await callback.message.edit_text("ℹ️ Нет активных записей.", reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📅 Записаться", callback_data="book")],
            [InlineKeyboardButton(text="↩️ Меню", callback_data="menu")]
        ]))
    await callback.answer()

@router.callback_query(F.data == "ignore")
async def ignore(callback: CallbackQuery):
    await callback.answer()

async def main():
    init_db()
    print("✅ Бот запущен! (Проверьте логи на хостинге)")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
