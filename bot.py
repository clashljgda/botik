import sqlite3
import logging
from datetime import datetime, date as date_type
from calendar import monthcalendar, month_name
from telebot import TeleBot, types

# ===========================================
# КОНФИГУРАЦИЯ — ЗАМЕНИТЕ НА СВОИ ЗНАЧЕНИЯ!
# ===========================================
BOT_TOKEN = "8576375750:AAFWQyd1fYTHcMOdTJwRp3Sxupd7q16CcN0"      # ← СЮДА ВСТАВЬТЕ ТОКЕН ОТ @BotFather
ADMIN_CHAT_ID = 1154349995         # ← СЮДА ВСТАВЬТЕ ВАШ ЧИСЛОВОЙ chat_id

# ===========================================
# ИНИЦИАЛИЗАЦИЯ
# ===========================================
logging.basicConfig(level=logging.INFO)
bot = TeleBot(BOT_TOKEN)

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
    return types.InlineKeyboardMarkup(keyboard)

# ===========================================
# ОБРАБОТЧИКИ
# ===========================================
@bot.message_handler(commands=['start'])
def start(message):
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton(text="📅 Записаться", callback_data="book"))
    markup.add(types.InlineKeyboardButton(text="❌ Отменить запись", callback_data="cancel"))
    bot.send_message(
        message.chat.id,
        "👋 Привет! Я бот для записи на тренировки.\n\n"
        "💪 Выберите действие:",
        reply_markup=markup
    )

@bot.callback_query_handler(func=lambda call: call.data == "menu")
def menu(call):
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton(text="📅 Записаться", callback_data="book"))
    markup.add(types.InlineKeyboardButton(text="❌ Отменить запись", callback_data="cancel"))
    bot.edit_message_text(
        "Главное меню:",
        call.message.chat.id,
        call.message.message_id,
        reply_markup=markup
    )
    bot.answer_callback_query(call.id)

@bot.callback_query_handler(func=lambda call: call.data == "book")
def book(call):
    now = datetime.now()
    markup = generate_calendar(now.year, now.month, get_booked_dates(now.month, now.year))
    bot.edit_message_text(
        "📅 Выберите дату тренировки:\n"
        "✅ — свободно | ❌ — занято | — — прошло",
        call.message.chat.id,
        call.message.message_id,
        reply_markup=markup
    )
    bot.answer_callback_query(call.id)

@bot.callback_query_handler(func=lambda call: call.data.startswith("cal_nav_"))
def nav(call):
    _, _, y, m = call.data.split("_")
    y, m = int(y), int(m)
    markup = generate_calendar(y, m, get_booked_dates(m, y))
    bot.edit_message_text(
        "📅 Выберите дату тренировки:\n"
        "✅ — свободно | ❌ — занято | — — прошло",
        call.message.chat.id,
        call.message.message_id,
        reply_markup=markup
    )
    bot.answer_callback_query(call.id)

@bot.callback_query_handler(func=lambda call: call.data.startswith("cal_day_"))
def pick_date(call):
    date_str = call.data.split("_")[2]
    try:
        selected = datetime.strptime(date_str, "%Y-%m-%d").date()
        if selected < datetime.now().date():
            bot.answer_callback_query(call.id, "❌ Нельзя выбрать прошедшую дату!", show_alert=True)
            return
    except:
        bot.answer_callback_query(call.id, "❌ Ошибка даты", show_alert=True)
        return
    
    fmt = selected.strftime("%d.%m.%Y (%A)").capitalize()
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton(text="✅ Подтвердить запись", callback_data=f"confirm_{date_str}"))
    markup.add(types.InlineKeyboardButton(text="↩️ Выбрать другую дату", callback_data="book"))
    bot.edit_message_text(
        f"Вы выбрали: {fmt}\n\nПодтвердить запись?",
        call.message.chat.id,
        call.message.message_id,
        reply_markup=markup
    )
    bot.answer_callback_query(call.id)

@bot.callback_query_handler(func=lambda call: call.data.startswith("confirm_"))
def confirm(call):
    date_str = call.data.split("_")[1]
    user_id = call.from_user.id
    username = call.from_user.username or f"id{user_id}"
    
    # Отменяем старую запись, если есть
    existing = get_user_booking(user_id)
    if existing and existing != date_str:
        cancel_booking(user_id)
    
    if not book_training(user_id, username, date_str):
        now = datetime.now()
        markup = generate_calendar(now.year, now.month, get_booked_dates(now.month, now.year))
        bot.edit_message_text(
            "❌ Эта дата уже занята. Выберите другую:",
            call.message.chat.id,
            call.message.message_id,
            reply_markup=markup
        )
        return
    
    # Форматируем дату для сообщения
    fmt = datetime.strptime(date_str, "%Y-%m-%d").strftime("%d.%m.%Y")
    
    # Уведомляем админа
    try:
        bot.send_message(
            ADMIN_CHAT_ID,
            f"🔔 НОВАЯ ЗАПИСЬ НА ТРЕНИРОВКУ!\n\n"
            f"👤 Пользователь: @{username} (ID: {user_id})\n"
            f"📅 Дата: {fmt}\n"
            f"⏰ Время: 19:00\n"
            f"📍 Место: ул. Спортивная, 15"
        )
    except Exception as e:
        logging.error(f"Не удалось отправить админу: {e}")
    
    # Отвечаем пользователю
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton(text="❌ Отменить запись", callback_data="cancel"))
    markup.add(types.InlineKeyboardButton(text="↩️ В меню", callback_data="menu"))
    bot.edit_message_text(
        f"✅ Успешно записаны на тренировку!\n\n"
        f"📅 Дата: {fmt}\n"
        f"⏰ Время: 19:00\n"
        f"📍 Адрес: ул. Спортивная, 15\n\n"
        f"❗ За 3 часа до тренировки можно отменить запись через меню бота.",
        call.message.chat.id,
        call.message.message_id,
        reply_markup=markup
    )
    bot.answer_callback_query(call.id)

@bot.callback_query_handler(func=lambda call: call.data == "cancel")
def cancel(call):
    date = cancel_booking(call.from_user.id)
    if date:
        fmt = datetime.strptime(date, "%Y-%m-%d").strftime("%d.%m.%Y")
        try:
            username = call.from_user.username or f"id{call.from_user.id}"
            bot.send_message(
                ADMIN_CHAT_ID,
                f"🔕 ОТМЕНА ЗАПИСИ\n\n"
                f"👤 Пользователь: @{username}\n"
                f"📅 Дата: {fmt}"
            )
        except:
            pass
        
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton(text="📅 Записаться снова", callback_data="book"))
        markup.add(types.InlineKeyboardButton(text="↩️ В меню", callback_data="menu"))
        bot.edit_message_text(
            f"❌ Ваша запись на {fmt} отменена.",
            call.message.chat.id,
            call.message.message_id,
            reply_markup=markup
        )
    else:
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton(text="📅 Записаться", callback_data="book"))
        markup.add(types.InlineKeyboardButton(text="↩️ В меню", callback_data="menu"))
        bot.edit_message_text(
            "ℹ️ У вас нет активных записей на тренировки.",
            call.message.chat.id,
            call.message.message_id,
            reply_markup=markup
        )
    bot.answer_callback_query(call.id)

@bot.callback_query_handler(func=lambda call: call.data == "ignore")
def ignore(call):
    bot.answer_callback_query(call.id)

# ===========================================
# ЗАПУСК
# ===========================================
if __name__ == '__main__':
    init_db()
    print("✅ Бот запущен! (pyTelegramBotAPI)")
    print(f"ℹ️  Токен: {'*' * (len(BOT_TOKEN)-4) + BOT_TOKEN[-4:] if BOT_TOKEN != 'YOUR_BOT_TOKEN' else 'НЕ УСТАНОВЛЕН'}")
    print(f"ℹ️  Админ: {ADMIN_CHAT_ID}")
    bot.infinity_polling()
