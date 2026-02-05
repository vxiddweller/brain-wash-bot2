import os
import logging
import sqlite3
import random
import logging
import sys
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
    MessageHandler,
    filters
)

# ==================== НАСТРОЙКИ ====================
# Настройка логирования в файл
file_handler = logging.FileHandler('bot.log', encoding='utf-8')
file_handler.setLevel(logging.INFO)
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
file_handler.setFormatter(formatter)

logger = logging.getLogger()
logger.addHandler(file_handler)

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

import http.server
import socketserver
import threading

class HealthHandler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/health' or self.path == '/':
            self.send_response(200)
            self.send_header('Content-type', 'text/plain')
            self.end_headers()
            self.wfile.write(b'✅ Roblox Brain Wash Bot OK!')
        else:
            self.send_response(404)
            self.end_headers()
    
    def log_message(self, format, *args):
        pass

def run_health_server():
    try:
        port = int(os.environ.get('PORT', 8080))
        with socketserver.TCPServer(("0.0.0.0", port), HealthHandler) as httpd:
            logger.info(f"✅ Health server running on port {port}")
            httpd.serve_forever()
    except Exception as e:
        logger.error(f"❌ Health server error: {e}")

health_thread = threading.Thread(target=run_health_server, daemon=True)
health_thread.start()

# Запускаем в отдельном потоке
flask_thread = Thread(target=run_flask, daemon=True)
flask_thread.start()

# Получаем токен бота
TOKEN = os.environ.get("BOT_TOKEN")
if not TOKEN:
    logger.error("⚠️ Ошибка: Нет токена!")
    exit(1)

# ID админа (ЗАМЕНИ НА СВОЙ!)
ADMIN_IDS = [1032908366]  # ← ВСТАВЬ СВОЙ TELEGRAM ID!

# Настройки записи
WORKING_HOURS = [10, 12, 14, 16, 18, 20]  # Часы приема
DAYS_AHEAD = 7                             # Запись на 7 дней

# ==================== БАЗА ДАННЫХ ====================
DB_NAME = "roblox_wash.db"

def init_database():
    """Инициализация базы данных"""
    try:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS appointments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date TEXT NOT NULL,
                time TEXT NOT NULL,
                service_type TEXT NOT NULL,
                user_id INTEGER,
                user_name TEXT,
                user_phone TEXT,
                status TEXT DEFAULT 'free',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(date, time)
            )
        ''')
        
        cursor.execute("SELECT COUNT(*) FROM appointments WHERE date >= date('now')")
        count = cursor.fetchone()[0]
        
        if count == 0:
            logger.info("Создаю расписание в Roblox...")
            generate_schedule(cursor)
        
        conn.commit()
        conn.close()
        logger.info("✅ База Roblox готова!")
        
    except Exception as e:
        logger.error(f"❌ Ошибка: {e}")

def generate_schedule(cursor):
    """Генерация расписания"""
    today = datetime.now()
    appointments = []
    
    # Услуги в Roblox стиле
    services = [
        ("🧹 Базовая чистка чата", "basic", 500),      # 500 робуксов
        ("🌀 Очистка от нообов", "deep", 1200),        # 1200 робуксов
        ("⚡ Экспресс-фикс багов", "express", 300),    # 300 робуксов
        ("👑 VIP разблокировка", "vip", 2500),         # 2500 робуксов
        ("🎮 Прокачка скиллов", "pro", 1800),          # 1800 робуксов
        ("🔧 Ремонт аватара", "avatar", 800)           # 800 робуксов
    ]
    
    import random
    
    for day in range(DAYS_AHEAD):
        appointment_date = today + timedelta(days=day + 1)
        date_str = appointment_date.strftime("%Y-%m-%d")
        
        for hour in WORKING_HOURS:
            time_str = f"{hour:02d}:00"
            service = random.choice(services)
            
            appointments.append((
                date_str,
                time_str,
                service[1],
                None,
                None,
                None,
                'free'
            ))
    
    cursor.executemany('''
        INSERT OR IGNORE INTO appointments 
        VALUES (?, ?, ?, ?, ?, ?, ?)
    ''', appointments)

def get_russian_day_name(weekday):
    """Дни недели"""
    days = ["Понедельник", "Вторник", "Среда", "Четверг", "Пятница", "Суббота", "Воскресенье"]
    return days[weekday]

# ==================== ФУНКЦИИ БАЗЫ ====================
def get_available_dates():
    """Свободные даты"""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT DISTINCT date 
        FROM appointments 
        WHERE status = 'free' AND date >= date('now')
        ORDER BY date
        LIMIT 10
    ''')
    
    dates = [row[0] for row in cursor.fetchall()]
    conn.close()
    return dates

def get_available_times(date):
    """Свободное время на дату"""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT time, service_type 
        FROM appointments 
        WHERE date = ? AND status = 'free'
        ORDER BY time
    ''', (date,))
    
    times = cursor.fetchall()
    conn.close()
    return times

def get_service_info(service_code):
    """Инфо об услуге"""
    services = {
        'basic': ('🧹 Базовая чистка чата', 500, "Удаление спама, токсичных друзей, мусорных сообщений"),
        'deep': ('🌀 Очистка от нообов', 1200, "Полное удаление нообского мышления, апгрейд скиллов"),
        'express': ('⚡ Экспресс-фикс багов', 300, "Срочное исправление багов в логике, быстрая помощь"),
        'vip': ('👑 VIP разблокировка', 2500, "Разблокировка премиум-возможностей, доступ к секретным зонам"),
        'pro': ('🎮 Прокачка скиллов', 1800, "Повышение уровня, изучение новых механик, гайды от про"),
        'avatar': ('🔧 Ремонт аватара', 800, "Починка аватара, настройка анимаций, новые аксессуары")
    }
    return services.get(service_code, ('Неизвестная услуга', 0, ""))

def book_appointment(date, time, user_id, user_name, phone=None):
    """Бронирование"""
    try:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        
        cursor.execute('''
            UPDATE appointments 
            SET user_id = ?, user_name = ?, user_phone = ?, status = 'booked'
            WHERE date = ? AND time = ? AND status = 'free'
        ''', (user_id, user_name, phone, date, time))
        
        success = cursor.rowcount > 0
        conn.commit()
        conn.close()
        
        return success
    except Exception as e:
        logger.error(f"Ошибка: {e}")
        return False

def get_user_appointments(user_id):
    """Записи пользователя"""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT date, time, service_type, created_at 
        FROM appointments 
        WHERE user_id = ? 
        ORDER BY date, time
    ''', (user_id,))
    
    appointments = cursor.fetchall()
    conn.close()
    return appointments

def get_all_bookings():
    """ВСЕ записи (для админа)"""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT date, time, service_type, user_name, user_phone, created_at 
        FROM appointments 
        WHERE status = 'booked'
        ORDER BY date, time
    ''')
    
    bookings = cursor.fetchall()
    conn.close()
    return bookings

def get_stats():
    """Статистика (для админа)"""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    # Общая статистика
    cursor.execute("SELECT COUNT(*) FROM appointments")
    total = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM appointments WHERE status = 'free'")
    free = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM appointments WHERE status = 'booked'")
    booked = cursor.fetchone()[0]
    
    # Статистика по услугам
    cursor.execute('''
        SELECT service_type, COUNT(*) 
        FROM appointments 
        WHERE status = 'booked'
        GROUP BY service_type
    ''')
    service_stats = cursor.fetchall()
    
    conn.close()
    
    return {
        'total': total,
        'free': free,
        'booked': booked,
        'services': service_stats
    }

# ==================== КЛАВИАТУРЫ ====================
def get_main_menu(user_id):
    """Главное меню"""
    keyboard = [
        [InlineKeyboardButton("🎮 Свободные слоты", callback_data="view_slots")],
        [InlineKeyboardButton("📅 Записаться на чистку", callback_data="book")],
        [InlineKeyboardButton("📋 Мои записи", callback_data="my_bookings")],
        [InlineKeyboardButton("💎 Услуги и цены", callback_data="services")],
        [InlineKeyboardButton("🏢 О сервисе", callback_data="about")],
        [InlineKeyboardButton("📞 Контакты", callback_data="contacts")],
    ]
    
    # Если админ - добавляем кнопку
    if user_id in ADMIN_IDS:
        keyboard.append([InlineKeyboardButton("👑 ПАНЕЛЬ АДМИНА", callback_data="admin_panel")])
    
    return InlineKeyboardMarkup(keyboard)

def get_admin_menu():
    """Меню админа"""
    keyboard = [
        [InlineKeyboardButton("📊 Статистика", callback_data="admin_stats")],
        [InlineKeyboardButton("📋 Все записи", callback_data="admin_all")],
        [InlineKeyboardButton("🔄 Обновить расписание", callback_data="admin_refresh")],
        [InlineKeyboardButton("🏠 В главное меню", callback_data="back_main")]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_dates_keyboard(dates):
    """Клавиатура с датами"""
    keyboard = []
    
    for date_str in dates:
        date_obj = datetime.strptime(date_str, "%Y-%m-%d")
        day_name = get_russian_day_name(date_obj.weekday())
        button_text = f"{date_obj.strftime('%d.%m')} ({day_name[:3]})"
        
        keyboard.append([InlineKeyboardButton(button_text, callback_data=f"date_{date_str}")])
    
    keyboard.append([
        InlineKeyboardButton("◀️ Назад", callback_data="back_main"),
        InlineKeyboardButton("🔄 Обновить", callback_data="view_slots")
    ])
    
    return InlineKeyboardMarkup(keyboard)

def get_times_keyboard(times, selected_date):
    """Клавиатура со временем"""
    keyboard = []
    
    for time_str, service_code in times:
        service_name, price, _ = get_service_info(service_code)
        short_name = service_name.split()[1]
        button_text = f"{time_str} - {short_name} ({price} 🪙)"
        
        keyboard.append([
            InlineKeyboardButton(button_text, callback_data=f"time_{selected_date}_{time_str}_{service_code}")
        ])
    
    keyboard.append([
        InlineKeyboardButton("◀️ Другие даты", callback_data="book"),
        InlineKeyboardButton("🏠 В меню", callback_data="back_main")
    ])
    
    return InlineKeyboardMarkup(keyboard)

def get_confirm_keyboard(date, time, service_code):
    """Подтверждение"""
    keyboard = [
        [
            InlineKeyboardButton("✅ Да, записать!", callback_data=f"confirm_{date}_{time}_{service_code}"),
            InlineKeyboardButton("❌ Отмена", callback_data="book")
        ]
    ]
    return InlineKeyboardMarkup(keyboard)

# ==================== ОБРАБОТЧИКИ ====================
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /start"""
    user = update.effective_user
    
    welcome_text = f"""
🎮 *Добро пожаловать в Roblox Brain Wash, {user.first_name}!* 

*Твой мозг заспамлен?* 
*Чат полон токсиков?* 
*Мышление как у нооба?*

✨ *Мы поможем!* ✨

*Наш сервис предлагает:*
• 🧹 Чистку чата от спама
• 🌀 Удаление нообского мышления  
• ⚡ Фикс багов в логике
• 👑 VIP разблокировки
• 🎮 Прокачку скиллов

*Выбери действие ниже и давай кайфанем!* 😎
    """
    
    # Инициализация БД
    if 'db_initialized' not in context.bot_data:
        init_database()
        context.bot_data['db_initialized'] = True
    
    await update.message.reply_text(
        welcome_text,
        reply_markup=get_main_menu(user.id),
        parse_mode='Markdown'
    )

async def view_slots(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Просмотр слотов"""
    query = update.callback_query
    await query.answer()
    
    available_dates = get_available_dates()
    
    if not available_dates:
        await query.edit_message_text(
            "😔 *На этой неделе все слоты заняты!*\n\n"
            "Но не расстраивайся! Можешь:\n"
            "1️⃣ Подписаться на уведомления о новых слотах\n"
            "2️⃣ Написать нашему администратору @RobloxProCleaner\n"
            "3️⃣ Попробовать зайти позже\n\n"
            "*Скоро будут новые слоты!* ⚡",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔄 Проверить снова", callback_data="view_slots")],
                [InlineKeyboardButton("🏠 В меню", callback_data="back_main")]
            ]),
            parse_mode='Markdown'
        )
        return
    
    # Форматируем даты
    dates_text = ""
    for date_str in available_dates:
        date_obj = datetime.strptime(date_str, "%Y-%m-%d")
        day_name = get_russian_day_name(date_obj.weekday())
        dates_text += f"• *{date_obj.strftime('%d.%m.%Y')}* ({day_name})\n"
    
    await query.edit_message_text(
        f"🎯 *Доступные даты для записи:*\n\n"
        f"{dates_text}\n"
        f"*Выбери дату и посмотрим свободное время:* ⤵️",
        reply_markup=get_dates_keyboard(available_dates),
        parse_mode='Markdown'
    )

async def select_date(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Выбор даты"""
    query = update.callback_query
    await query.answer()
    
    date_str = query.data.replace("date_", "")
    date_obj = datetime.strptime(date_str, "%Y-%m-%d")
    day_name = get_russian_day_name(date_obj.weekday())
    
    available_times = get_available_times(date_str)
    
    if not available_times:
        await query.edit_message_text(
            f"📅 *{date_obj.strftime('%d.%m.%Y')} ({day_name})*\n\n"
            "😅 *Все слоты на эту дату уже заняты!*\n\n"
            "Геймеры быстро разбирают лучшие время!\n"
            "Попробуй другую дату:",
            reply_markup=get_dates_keyboard(get_available_dates()),
            parse_mode='Markdown'
        )
        return
    
    # Статистика по услугам
    service_stats = {}
    for _, service_code in available_times:
        service_name, price, _ = get_service_info(service_code)
        short_name = service_name.split()[1]
        service_stats[short_name] = service_stats.get(short_name, 0) + 1
    
    stats_text = "\n".join([f"• {name}: {count} слотов" for name, count in service_stats.items()])
    
    await query.edit_message_text(
        f"⏰ *Свободные слоты на {date_obj.strftime('%d.%m.%Y')} ({day_name}):*\n\n"
        f"📊 *Доступные услуги:*\n{stats_text}\n\n"
        f"*Выбери удобное время:* ⤵️",
        reply_markup=get_times_keyboard(available_times, date_str),
        parse_mode='Markdown'
    )

async def select_time(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Выбор времени"""
    query = update.callback_query
    await query.answer()
    
    data = query.data.replace("time_", "")
    date_str, time_str, service_code = data.split("_", 2)
    
    context.user_data['selected_time'] = time_str
    context.user_data['selected_service'] = service_code
    
    date_obj = datetime.strptime(date_str, "%Y-%m-%d")
    day_name = get_russian_day_name(date_obj.weekday())
    service_name, price, description = get_service_info(service_code)
    
    # Угарные названия услуг
    service_titles = {
        'basic': "🧹 *Базовая чистка чата*",
        'deep': "🌀 *Глубокая очистка от нообов*", 
        'express': "⚡ *Экспресс-фикс багов*",
        'vip': "👑 *VIP разблокировка*",
        'pro': "🎮 *Прокачка скиллов*",
        'avatar': "🔧 *Ремонт аватара*"
    }
    
    confirmation_text = f"""
{service_titles.get(service_code, '🎯 *Запись на процедуру*')}

*📅 Дата:* {date_obj.strftime('%d.%m.%Y')} ({day_name})
*⏰ Время:* {time_str}
*💰 Стоимость:* {price} 🪙 (робуксов)

*📝 Что входит:*
{description}

*📍 Локация проведения:*
Сервер **«Brain Clean HQ»**
Карта: **«Cleaning Facility»**
Портал: **#clean-zone-315**

*⏳ Длительность сеанса:* 45-60 минут

*Готов к чистке?* 🤖✨
    """
    
    await query.edit_message_text(
        confirmation_text,
        reply_markup=get_confirm_keyboard(date_str, time_str, service_code),
        parse_mode='Markdown'
    )

async def confirm_booking(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Подтверждение записи"""
    query = update.callback_query
    await query.answer()
    
    data = query.data.replace("confirm_", "")
    date_str, time_str, service_code = data.split("_", 2)
    
    user = query.from_user
    user_name = user.full_name or user.first_name
    
    success = book_appointment(date_str, time_str, user.id, user_name)
    
    if success:
        date_obj = datetime.strptime(date_str, "%Y-%m-%d")
        day_name = get_russian_day_name(date_obj.weekday())
        service_name, price, _ = get_service_info(service_code)
        
        success_text = f"""
🎉 *ТЫ ЗАПИСАН! LET'S GOOO!* 🚀

*🎮 Детали записи:*
• Услуга: {service_name}
• Дата: {date_obj.strftime('%d.%m.%Y')} ({day_name})
• Время: {time_str}
• Стоимость: {price} 🪙
• Твой ник: {user_name}
• ID записи: `{date_str}_{time_str}`

*📍 Как попасть на сервер:*
1. Зайди в Roblox
2. Найди сервер **«Brain Clean HQ»**
3. Используй код доступа: **#clean-{date_str.replace('-', '')}**
4. Подойди к NPC с именем **«Доктор Нейрочист»**

*📱 Наши контакты:*
• Админ: @RobloxProCleaner
• Техподдержка: @RobloxSupportBot
• Discord: discord.gg/robloxclean

*⚠️ Важно:*
• Приходи за 5-10 минут до начала
• Имей свободные 60 минут
• Бери с собой хорошее настроение!

*Удачи в прокачке мозга!* 🧠⚡
        """
        
        keyboard = [
            [InlineKeyboardButton("📋 Мои записи", callback_data="my_bookings")],
            [InlineKeyboardButton("🎮 Еще записаться", callback_data="book")],
            [InlineKeyboardButton("🏠 В меню", callback_data="back_main")]
        ]
        
        await query.edit_message_text(
            success_text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )
    else:
        await query.edit_message_text(
            "😱 *ОШИБКА! Этот слот уже занят!*\n\n"
            "Кто-то опередил тебя! 😅\n"
            "Выбери другое время пока оно свободно!",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("📅 Выбрать дату", callback_data="book")],
                [InlineKeyboardButton("🏠 В меню", callback_data="back_main")]
            ]),
            parse_mode='Markdown'
        )

async def my_bookings(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Мои записи"""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    appointments = get_user_appointments(user_id)
    
    if not appointments:
        await query.edit_message_text(
            "📭 *У тебя пока нет записей!*\n\n"
            "Хочешь прокачать свой мозг в Roblox? 🎮\n"
            "Запишись на чистку и стань про-геймером! ⚡",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🎮 Записаться", callback_data="book")],
                [InlineKeyboardButton("💎 Услуги", callback_data="services")],
                [InlineKeyboardButton("🏠 В меню", callback_data="back_main")]
            ]),
            parse_mode='Markdown'
        )
        return
    
    bookings_text = "📋 *Твои активные записи:*\n\n"
    
    for i, (date_str, time_str, service_code, created_at) in enumerate(appointments, 1):
        date_obj = datetime.strptime(date_str, "%Y-%m-%d")
        day_name = get_russian_day_name(date_obj.weekday())
        service_name, price, _ = get_service_info(service_code)
        
        bookings_text += f"*{i}. {service_name}*\n"
        bookings_text += f"   📅 {date_obj.strftime('%d.%m.%Y')} ({day_name[:3]})\n"
        bookings_text += f"   ⏰ {time_str} | 💰 {price} 🪙\n"
        bookings_text += f"   🆔 `{date_str}_{time_str}`\n\n"
    
    bookings_text += "*Для отмены напиши:* @RobloxProCleaner"
    
    keyboard = [
        [InlineKeyboardButton("🎮 Новая запись", callback_data="book")],
        [InlineKeyboardButton("📅 Свободные слоты", callback_data="view_slots")],
        [InlineKeyboardButton("🏠 В меню", callback_data="back_main")]
    ]
    
    await query.edit_message_text(
        bookings_text,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='Markdown'
    )

async def show_services(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Услуги и цены"""
    query = update.callback_query
    await query.answer()
    
    services_text = """
💎 *УСЛУГИ И ЦЕНЫ В ROBLOX 🪙*

*1. 🧹 БАЗОВАЯ ЧИСТКА ЧАТА (500 🪙)*
• Удаление спама и флуда
• Чистка друзей-токсиков  
• Настройка приватности
• Базовая защита

*2. 🌀 ОЧИСТКА ОТ НООБОВ (1200 🪙)*
• Полное удаление нообского мышления
• Установка про-логики
• Апгрейд скиллов принятия решений
• Защита от кринжа

*3. ⚡ ЭКСПРЕСС-ФИКС БАГОВ (300 🪙)*
• Срочное исправление логических ошибок
• Починка когнитивных функций
• Быстрая помощь при лагах
• Экстренная перезагрузка

*4. 👑 VIP РАЗБЛОКИРОВКА (2500 🪙)*
• Доступ к скрытым возможностям
• Премиум настройки мозга
• Эксклюзивные анимации
• Личный помощник-бот

*5. 🎮 ПРОКАЧКА СКИЛЛОВ (1800 🪙)*
• Повышение уровня реакции
• Изучение продвинутых механик
• Тренировка стратегического мышления
• Гайды от топ-геймеров

*6. 🔧 РЕМОНТ АВАТАРА (800 🪙)*
• Починка сломанных эмоций
• Настройка анимаций личности
• Новые аксессуары для ума
• Кастомизация поведения

*🎯 БОНУС: При записи на 2+ услуги - скидка 15%!*
    """
    
    await query.edit_message_text(
        services_text,
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🎮 Записаться", callback_data="book")],
            [InlineKeyboardButton("📅 Слоты", callback_data="view_slots")],
            [InlineKeyboardButton("🏠 В меню", callback_data="back_main")]
        ]),
        parse_mode='Markdown'
    )

async def about_service(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """О сервисе"""
    query = update.callback_query
    await query.answer()
    
    about_text = """
🏢 *ROBLOX BRAIN WASH SERVICE*

*Наша миссия:* 
Делаем геймеров лучше, чище и умнее! 🧠✨

*Основатели:*
• **Доктор Нейрочист** - главный специалист по чистке
• **Профессор Логикон** - эксперт по исправлению багов  
• **Мастер Скиллз** - тренер по прокачке
• **Аватар-Док** - специалист по ремонту аватаров

*Наши достижения:*
✅ 10,000+ довольных геймеров
✅ 99.7% успешных чисток
✅ Средний рост скиллов: +47%
✅ Лучший сервис 2024 по версии Roblox Times

*Принципы работы:*
1. 🤖 Только AI-технологии
2. 🔒 Полная конфиденциальность  
3. ⚡ Мгновенные результаты
4. 🎮 Интеграция с Roblox API

*Отзывы геймеров:*
"После чистки стал топом в BedWars!" - NoobMaster69
"Наконец-то понимаю шутки в чате!" - ProGamer228
"Мой аватар теперь не кринжовый!" - CoolAvatarGirl

*Присоединяйся к комьюнити!* 🚀
    """
    
    await query.edit_message_text(
        about_text,
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("💎 Услуги", callback_data="services")],
            [InlineKeyboardButton("🎮 Записаться", callback_data="book")],
            [InlineKeyboardButton("🏠 В меню", callback_data="back_main")]
        ]),
        parse_mode='Markdown'
    )

async def show_contacts(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Контакты"""
    query = update.callback_query
    await query.answer()
    
    contacts_text = """
📞 *КОНТАКТЫ И ПОДДЕРЖКА*

*🎮 Основной сервер:*
Roblox → Поиск → «Brain Clean HQ»
Или прямая ссылка: roblox.com/games/brain-clean

*💬 Техподдержка:*
• Telegram: @RobloxProCleaner
• Discord: discord.gg/robloxclean
• VK: vk.com/robloxbrainwash
• Instagram: @roblox.clean.service

*📧 Почта:*
• Для записи: booking@robloxclean.com
• Для жалоб: abuse@robloxclean.com  
• Для сотрудничества: partners@robloxclean.com

*⏰ Часы работы сервиса:*
Круглосуточно 24/7 🕛
(Но записи только в рабочее время)

*🚨 Экстренная помощь:*
Если случился когнитивный краш или
ментальный лаг - пиши @RobloxEmergency

*💰 Партнерская программа:*
Приведи друга - получи 200 🪙 на счет!
Подробности: @RobloxPartnersBot
    """
    
    await query.edit_message_text(
        contacts_text,
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🎮 Записаться", callback_data="book")],
            [InlineKeyboardButton("💎 Услуги", callback_data="services")],
            [InlineKeyboardButton("🏠 В меню", callback_data="back_main")]
        ]),
        parse_mode='Markdown'
    )

# ==================== АДМИН ПАНЕЛЬ ====================
async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Панель администратора"""
    query = update.callback_query
    await query.answer()
    
    user = query.from_user
    if user.id not in ADMIN_IDS:
        await query.edit_message_text("🚫 Ты не админ!")
        return
    
    await query.edit_message_text(
        "👑 *ПАНЕЛЬ АДМИНИСТРАТОРА ROBLOX BRAIN WASH*\n\n"
        "*Доступные команды:*",
        reply_markup=get_admin_menu(),
        parse_mode='Markdown'
    )

async def admin_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Статистика для админа"""
    query = update.callback_query
    await query.answer()
    
    user = query.from_user
    if user.id not in ADMIN_IDS:
        await query.edit_message_text("🚫 Нет доступа!")
        return
    
    stats = get_stats()
    
    # Статистика по услугам
    services_text = ""
    for service_code, count in stats['services']:
        service_name, price, _ = get_service_info(service_code)
        short_name = service_name.split()[1]
        services_text += f"• {short_name}: {count} записей\n"
    
    stats_text = f"""
📊 *СТАТИСТИКА СЕРВИСА:*

*Общая статистика:*
• Всего слотов: {stats['total']}
• Свободно: {stats['free']}
• Забронировано: {stats['booked']}
• Заполненность: {(stats['booked']/stats['total']*100):.1f}%

*Популярность услуг:*
{services_text}

*💰 Оборот (если все оплачено):*
• Базовая: 500 🪙 × {next((c for s,c in stats['services'] if s=='basic'), 0)} = {500 * next((c for s,c in stats['services'] if s=='basic'), 0)} 🪙
• Глубокая: 1200 🪙 × {next((c for s,c in stats['services'] if s=='deep'), 0)} = {1200 * next((c for s,c in stats['services'] if s=='deep'), 0)} 🪙
• VIP: 2500 🪙 × {next((c for s,c in stats['services'] if s=='vip'), 0)} = {2500 * next((c for s,c in stats['services'] if s=='vip'), 0)} 🪙

*📈 ИТОГО: {sum(price * next((c for s,c in stats['services'] if s==code), 0) for code, (_, price, _) in get_service_info.__closure__[0].cell_contents.items() if any(s==code for s,_ in stats['services']))} 🪙*
    """
    
    await query.edit_message_text(
        stats_text,
        reply_markup=get_admin_menu(),
        parse_mode='Markdown'
    )

async def admin_all_bookings(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Все записи для админа"""
    query = update.callback_query
    await query.answer()
    
    user = query.from_user
    if user.id not in ADMIN_IDS:
        await query.edit_message_text("🚫 Нет доступа!")
        return
    
    bookings = get_all_bookings()
    
    if not bookings:
        await query.edit_message_text(
            "📭 *Нет активных записей*",
            reply_markup=get_admin_menu()
        )
        return
    
    bookings_text = "📋 *ВСЕ АКТИВНЫЕ ЗАПИСИ:*\n\n"
    
    for i, (date_str, time_str, service_code, user_name, phone, created_at) in enumerate(bookings[:15], 1):
        date_obj = datetime.strptime(date_str, "%Y-%m-%d")
        service_name, price, _ = get_service_info(service_code)
        short_name = service_name.split()[1]
        
        bookings_text += f"*{i}. {user_name or 'Аноним'}*\n"
        bookings_text += f"   📅 {date_obj.strftime('%d.%m')} в {time_str}\n"
        bookings_text += f"   🎮 {short_name} ({price} 🪙)\n"
        if phone:
            bookings_text += f"   📱 {phone}\n"
        bookings_text += f"   🕐 Запись: {created_at[:16]}\n\n"
    
    if len(bookings) > 15:
        bookings_text += f"\n*... и еще {len(bookings) - 15} записей*"
    
    await query.edit_message_text(
        bookings_text,
        reply_markup=get_admin_menu(),
        parse_mode='Markdown'
    )

async def admin_refresh(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обновить расписание (быстрая версия)"""
    query = update.callback_query
    await query.answer()
    
    user = query.from_user
    if user.id not in ADMIN_IDS:
        await query.edit_message_text("🚫 Нет доступа!")
        return
    
    # Быстрое сообщение
    await query.edit_message_text(
        "⏳ *Обновляю расписание...*",
        parse_mode='Markdown'
    )
    
    try:
        # БЫСТРЫЙ метод
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        
        # Удаляем только будущие записи
        cursor.execute("DELETE FROM appointments WHERE date >= date('now')")
        
        # Быстро генерируем новые
        today = datetime.now()
        services = [
            ("🧹 Базовая чистка чата", "basic", 500),
            ("🌀 Очистка от нообов", "deep", 1200),
            ("⚡ Экспресс-фикс багов", "express", 300),
            ("👑 VIP разблокировка", "vip", 2500),
            ("🎮 Прокачка скиллов", "pro", 1800),
            ("🔧 Ремонт аватара", "avatar", 800)
        ]
        
        WORKING_HOURS = [10, 12, 14, 16, 18, 20]
        appointments = []
        
        for day in range(7):
            appointment_date = today + timedelta(days=day + 1)
            date_str = appointment_date.strftime("%Y-%m-%d")
            
            for hour in WORKING_HOURS:
                time_str = f"{hour:02d}:00"
                service = random.choice(services)
                
                appointments.append((
                    date_str,
                    time_str,
                    service[1],
                    None,
                    None,
                    None,
                    'free'
                ))
        
        # Массовая вставка - БЫСТРО!
        cursor.executemany('''
            INSERT INTO appointments (date, time, service_type, user_id, user_name, user_phone, status)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', appointments)
        
        conn.commit()
        conn.close()
        
        # Сообщение об успехе
        await query.edit_message_text(
            "✅ *Готово! Расписание обновлено!*\n\n"
            f"📅 Создано: {len(appointments)} слотов\n"
            f"🎮 Услуг: {len(services)} видов\n"
            f"⏰ Часов в день: {len(WORKING_HOURS)}\n\n"
            "Теперь пользователи могут записываться на новую неделю! 🎮",
            reply_markup=get_admin_menu(),
            parse_mode='Markdown'
        )
        
    except Exception as e:
        logger.error(f"Ошибка при обновлении расписания: {e}")
        
        await query.edit_message_text(
            f"❌ *Ошибка при обновлении!*\n\n"
            f"*Причина:* {str(e)[:100]}\n\n"
            "Попробуйте позже или проверьте базу данных.",
            reply_markup=get_admin_menu(),
            parse_mode='Markdown'
        )

async def back_to_main(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """В главное меню"""
    query = update.callback_query
    await query.answer()
    
    user = query.from_user
    await query.edit_message_text(
        "🎮 *Главное меню Roblox Brain Wash*\n\n"
        "*Выбери действие:* ⤵️",
        reply_markup=get_main_menu(user.id),
        parse_mode='Markdown'
    )

# ==================== ОСНОВНАЯ ФУНКЦИЯ ====================
def main():
    """Запуск бота"""
    logger.info("🚀 Запускаю Roblox Brain Wash Bot...")
    
    # Инициализация БД
    init_database()
    
    # Создание приложения
    app = Application.builder().token(TOKEN).build()
    
    # Регистрация команд
    app.add_handler(CommandHandler("start", start_command))
    
    # Обработчики для пользователей
    app.add_handler(CallbackQueryHandler(view_slots, pattern="^view_slots$"))
    app.add_handler(CallbackQueryHandler(select_date, pattern="^date_"))
    app.add_handler(CallbackQueryHandler(select_time, pattern="^time_"))
    app.add_handler(CallbackQueryHandler(confirm_booking, pattern="^confirm_"))
    app.add_handler(CallbackQueryHandler(my_bookings, pattern="^my_bookings$"))
    app.add_handler(CallbackQueryHandler(show_services, pattern="^services$"))
    app.add_handler(CallbackQueryHandler(about_service, pattern="^about$"))
    app.add_handler(CallbackQueryHandler(show_contacts, pattern="^contacts$"))
    
    # Для кнопки "Записаться" - начинаем с выбора даты
    app.add_handler(CallbackQueryHandler(view_slots, pattern="^book$"))
    
    # Админ-обработчики
    app.add_handler(CallbackQueryHandler(admin_panel, pattern="^admin_panel$"))
    app.add_handler(CallbackQueryHandler(admin_stats, pattern="^admin_stats$"))
    app.add_handler(CallbackQueryHandler(admin_all_bookings, pattern="^admin_all$"))
    app.add_handler(CallbackQueryHandler(admin_refresh, pattern="^admin_refresh$"))
    
    # Навигация
    app.add_handler(CallbackQueryHandler(back_to_main, pattern="^back_main$"))
    
    # Обработчик текстовых сообщений
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, back_to_main))
    
    logger.info("✅ Roblox бот запущен и готов!")
    logger.info("🎮 Напиши /start в Telegram!")
    
    # Запуск бота
    app.run_polling()

if __name__ == "__main__":
    main()
