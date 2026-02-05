import os
import logging
import sqlite3
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
    MessageHandler,
    filters  # ← ИМЕННО ТАК в новой версии!
)

# ==================== НАСТРОЙКИ ====================
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Получаем токен бота
TOKEN = os.environ.get("BOT_TOKEN")
if not TOKEN:
    logger.error("⚠️ ОШИБКА: Не задан токен бота!")
    logger.error("ℹ️ Установите переменную окружения BOT_TOKEN")
    exit(1)

# Настройки записи
WORKING_HOURS = [10, 12, 14, 16, 18]  # Часы приема: 10:00, 12:00 и т.д.
DAYS_AHEAD = 7                         # Запись на 7 дней вперед
MINUTES_PER_SESSION = 60               # Длительность сеанса

# ==================== БАЗА ДАННЫХ ====================
DB_NAME = "brainwash_appointments.db"

def init_database():
    """Инициализация базы данных SQLite"""
    try:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        
        # Таблица для записей
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
        
        # Проверяем, есть ли уже записи на ближайшую неделю
        cursor.execute("SELECT COUNT(*) FROM appointments WHERE date >= date('now')")
        count = cursor.fetchone()[0]
        
        if count == 0:
            logger.info("Генерирую расписание на неделю вперед...")
            generate_schedule(cursor)
        
        conn.commit()
        conn.close()
        logger.info("✅ База данных готова!")
        
    except Exception as e:
        logger.error(f"❌ Ошибка инициализации БД: {e}")

def generate_schedule(cursor):
    """Генерация расписания на неделю вперед"""
    today = datetime.now()
    appointments = []
    
    # Типы услуг с ценами
    services = [
        ("🧠 Стандартная", "standart", 1500),
        ("🌀 Глубокая", "deep", 2500),
        ("⚡ Экспресс", "express", 1000),
        ("👑 VIP", "vip", 5000)
    ]
    
    import random
    
    for day in range(DAYS_AHEAD):
        appointment_date = today + timedelta(days=day + 1)  # Начиная с завтра
        date_str = appointment_date.strftime("%Y-%m-%d")
        day_name_rus = get_russian_day_name(appointment_date.weekday())
        
        for hour in WORKING_HOURS:
            time_str = f"{hour:02d}:00"
            service = random.choice(services)
            
            appointments.append((
                date_str,
                time_str,
                service[1],  # service code
                None,        # user_id
                None,        # user_name
                None,        # user_phone
                'free'       # status
            ))
    
    cursor.executemany('''
        INSERT OR IGNORE INTO appointments 
        (date, time, service_type, user_id, user_name, user_phone, status) 
        VALUES (?, ?, ?, ?, ?, ?, ?)
    ''', appointments)

def get_russian_day_name(weekday):
    """Получить название дня недели на русском"""
    days = ["Понедельник", "Вторник", "Среда", "Четверг", "Пятница", "Суббота", "Воскресенье"]
    return days[weekday]

# ==================== ФУНКЦИИ БАЗЫ ДАННЫХ ====================
def get_available_dates():
    """Получить даты, на которые есть свободные места"""
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
    """Получить свободное время на конкретную дату"""
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

def get_service_name(service_code):
    """Получить название услуги по коду"""
    services = {
        'standart': ('🧠 Стандартная промывка', 1500),
        'deep': ('🌀 Глубокая очистка', 2500),
        'express': ('⚡ Экспресс-сессия', 1000),
        'vip': ('👑 VIP комплекс', 5000)
    }
    return services.get(service_code, ('Неизвестная услуга', 0))

def book_appointment(date, time, user_id, user_name, phone=None):
    """Забронировать запись"""
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
        logger.error(f"Ошибка бронирования: {e}")
        return False

def get_user_appointments(user_id):
    """Получить записи пользователя"""
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

def cancel_appointment(date, time, user_id):
    """Отменить запись"""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    cursor.execute('''
        UPDATE appointments 
        SET user_id = NULL, user_name = NULL, user_phone = NULL, status = 'free'
        WHERE date = ? AND time = ? AND user_id = ?
    ''', (date, time, user_id))
    
    success = cursor.rowcount > 0
    conn.commit()
    conn.close()
    
    return success

# ==================== КЛАВИАТУРЫ ====================
def get_main_menu():
    """Главное меню"""
    keyboard = [
        [InlineKeyboardButton("📅 Посмотреть расписание", callback_data="view_schedule")],
        [InlineKeyboardButton("🔄 Записаться на прием", callback_data="book_appointment")],
        [InlineKeyboardButton("📋 Мои записи", callback_data="my_appointments")],
        [InlineKeyboardButton("💰 Услуги и цены", callback_data="services_info")],
        [InlineKeyboardButton("🏥 О клинике", callback_data="about_clinic")],
        [InlineKeyboardButton("☎️ Контакты", callback_data="contacts")],
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
        InlineKeyboardButton("◀️ Назад", callback_data="back_to_main"),
        InlineKeyboardButton("🔄 Обновить", callback_data="view_schedule")
    ])
    
    return InlineKeyboardMarkup(keyboard)

def get_times_keyboard(times, selected_date):
    """Клавиатура со временем"""
    keyboard = []
    
    for time_str, service_code in times:
        service_name, price = get_service_name(service_code)
        button_text = f"{time_str} - {service_name.split()[1]} ({price}₽)"
        
        keyboard.append([
            InlineKeyboardButton(button_text, callback_data=f"time_{selected_date}_{time_str}_{service_code}")
        ])
    
    keyboard.append([
        InlineKeyboardButton("◀️ Выбрать другую дату", callback_data="book_appointment"),
        InlineKeyboardButton("🏠 В меню", callback_data="back_to_main")
    ])
    
    return InlineKeyboardMarkup(keyboard)

def get_confirmation_keyboard(date, time, service_code):
    """Клавиатура подтверждения записи"""
    keyboard = [
        [
            InlineKeyboardButton("✅ Да, записать", callback_data=f"confirm_{date}_{time}_{service_code}"),
            InlineKeyboardButton("❌ Отмена", callback_data="book_appointment")
        ],
        [InlineKeyboardButton("📞 Предварительно позвонить", callback_data="need_call")]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_yes_no_keyboard():
    """Простая клавиатура Да/Нет"""
    keyboard = [
        [
            InlineKeyboardButton("✅ Да", callback_data="yes_phone"),
            InlineKeyboardButton("❌ Нет", callback_data="no_phone")
        ]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_services_keyboard():
    """Клавиатура с услугами"""
    keyboard = [
        [InlineKeyboardButton("🧠 Стандартная (60 мин) - 1500₽", callback_data="service_standart")],
        [InlineKeyboardButton("🌀 Глубокая (90 мин) - 2500₽", callback_data="service_deep")],
        [InlineKeyboardButton("⚡ Экспресс (30 мин) - 1000₽", callback_data="service_express")],
        [InlineKeyboardButton("👑 VIP (120 мин) - 5000₽", callback_data="service_vip")],
        [InlineKeyboardButton("◀️ Назад", callback_data="back_to_main")]
    ]
    return InlineKeyboardMarkup(keyboard)

# ==================== ОБРАБОТЧИКИ КОМАНД ====================
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /start"""
    user = update.effective_user
    
    welcome_text = f"""
👋 *Добро пожаловать, {user.first_name}!*

*Brain Wash Clinic* — современная клиника промывки мозгов! 🧠✨

*Возможности бота:*
• 📅 *Просмотр расписания* — смотрите свободные окна
• 🔄 *Онлайн-запись* — бронируйте удобное время
• 📋 *Мои записи* — управляйте бронированиями
• 💰 *Услуги* — выбирайте подходящую программу
• 🏥 *Информация* — узнайте о клинике больше

*Выберите действие в меню ниже:* ⤵️
    """
    
    # Инициализируем БД при первом запуске
    if 'db_initialized' not in context.bot_data:
        init_database()
        context.bot_data['db_initialized'] = True
    
    await update.message.reply_text(
        welcome_text,
        reply_markup=get_main_menu(),
        parse_mode='Markdown'
    )

async def view_schedule(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать расписание"""
    query = update.callback_query
    await query.answer()
    
    available_dates = get_available_dates()
    
    if not available_dates:
        await query.edit_message_text(
            "📅 *Расписание на неделю*\n\n"
            "😔 На данный момент *нет свободных окон*.\n\n"
            "Пожалуйста, попробуйте позже или свяжитесь с администратором.\n\n"
            "📞 Контакт для срочной записи: +7 (XXX) XXX-XX-XX",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔄 Обновить", callback_data="view_schedule")],
                [InlineKeyboardButton("🏠 Главное меню", callback_data="back_to_main")]
            ]),
            parse_mode='Markdown'
        )
        return
    
    # Форматируем даты для отображения
    dates_text = ""
    for date_str in available_dates:
        date_obj = datetime.strptime(date_str, "%Y-%m-%d")
        day_name = get_russian_day_name(date_obj.weekday())
        dates_text += f"• *{date_obj.strftime('%d.%m.%Y')}* ({day_name})\n"
    
    total_free = len(get_available_times(available_dates[0])) if available_dates else 0
    
    await query.edit_message_text(
        f"📅 *Свободные дни для записи:*\n\n"
        f"{dates_text}\n"
        f"📊 *Всего свободных окон:* {total_free}\n\n"
        f"*Выберите дату для просмотра времени:* ⤵️",
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
            "😔 На эту дату *нет свободных окон*.\n\n"
            "Пожалуйста, выберите другую дату:",
            reply_markup=get_dates_keyboard(get_available_dates()),
            parse_mode='Markdown'
        )
        return
    
    # Сохраняем выбранную дату в контексте
    context.user_data['selected_date'] = date_str
    
    # Считаем статистику по услугам
    service_stats = {}
    for _, service_code in available_times:
        service_name, price = get_service_name(service_code)
        short_name = service_name.split()[1]
        service_stats[short_name] = service_stats.get(short_name, 0) + 1
    
    stats_text = "\n".join([f"• {name}: {count}" for name, count in service_stats.items()])
    
    await query.edit_message_text(
        f"⏰ *Доступное время на {date_obj.strftime('%d.%m.%Y')} ({day_name}):*\n\n"
        f"📊 *Доступные услуги:*\n{stats_text}\n\n"
        f"*Выберите удобное время:* ⤵️",
        reply_markup=get_times_keyboard(available_times, date_str),
        parse_mode='Markdown'
    )

async def select_time(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Выбор времени и услуги"""
    query = update.callback_query
    await query.answer()
    
    # Формат: time_2024-01-15_14:00_standart
    data = query.data.replace("time_", "")
    date_str, time_str, service_code = data.split("_", 2)
    
    # Сохраняем в контексте
    context.user_data['selected_time'] = time_str
    context.user_data['selected_service'] = service_code
    
    date_obj = datetime.strptime(date_str, "%Y-%m-%d")
    day_name = get_russian_day_name(date_obj.weekday())
    service_name, price = get_service_name(service_code)
    
    # Описание услуг
    service_descriptions = {
        'standart': "Базовая промывка от негативных мыслей",
        'deep': "Полная перезагрузка сознания",
        'express': "Быстрая очистка для срочных случаев",
        'vip': "Индивидуальная программа с психологом"
    }
    
    confirmation_text = f"""
✅ *Подтверждение записи*

*📅 Дата:* {date_obj.strftime('%d.%m.%Y')} ({day_name})
*⏰ Время:* {time_str}
*🧠 Услуга:* {service_name}
*💰 Стоимость:* {price}₽

*📝 Описание:*
{service_descriptions.get(service_code, 'Профессиональная промывка мозгов')}

*📍 Адрес клиники:*
ул. Мыслительная, д. 42, кабинет 315
(метро «Прозрение», 5 минут пешком)

*⏳ Длительность сеанса:* {MINUTES_PER_SESSION} минут

*Подтверждаете запись?*
    """
    
    await query.edit_message_text(
        confirmation_text,
        reply_markup=get_confirmation_keyboard(date_str, time_str, service_code),
        parse_mode='Markdown'
    )

async def confirm_booking(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Подтверждение записи"""
    query = update.callback_query
    await query.answer()
    
    if query.data.startswith("need_call"):
        await query.edit_message_text(
            "📞 *Нужен ли вам предварительный звонок?*\n\n"
            "Наш специалист свяжется с вами за 1 час до приема "
            "для уточнения деталей.",
            reply_markup=get_yes_no_keyboard(),
            parse_mode='Markdown'
        )
        return
    
    if query.data.startswith("yes_phone"):
        context.user_data['need_call'] = True
        await ask_for_phone(update, context)
        return
    
    if query.data.startswith("no_phone"):
        context.user_data['need_call'] = False
        await ask_for_phone(update, context)
        return
    
    # Если это прямое подтверждение
    if query.data.startswith("confirm_"):
        data = query.data.replace("confirm_", "")
        date_str, time_str, service_code = data.split("_", 2)
        
        user = query.from_user
        user_name = user.full_name or user.first_name
        
        # Пытаемся забронировать
        success = book_appointment(date_str, time_str, user.id, user_name)
        
        if success:
            date_obj = datetime.strptime(date_str, "%Y-%m-%d")
            day_name = get_russian_day_name(date_obj.weekday())
            service_name, price = get_service_name(service_code)
            
            success_text = f"""
🎉 *Запись успешно оформлена!*

*📋 Детали записи:*
• 🧠 Услуга: {service_name}
• 📅 Дата: {date_obj.strftime('%d.%m.%Y')} ({day_name})
• ⏰ Время: {time_str}
• 💰 Стоимость: {price}₽
• 👤 Имя: {user_name}
• 🆔 Номер записи: {date_str}_{time_str}

*📍 Адрес клиники:*
ул. Мыслительная, д. 42, 3 этаж, кабинет 315
Кодовый замок: #315#

*📞 Контакты:*
• Телефон: +7 (XXX) XXX-XX-XX
• Telegram: @brainwash_support
• Email: brainwash@clinic.ru

*📝 Важно:*
1. Приходите за 10 минут до начала
2. Возьмите с собой паспорт
3. Отмена возможна за 24 часа

*Спасибо за выбор нашей клиники!* 🧠✨
            """
            
            keyboard = [
                [InlineKeyboardButton("📋 Мои записи", callback_data="my_appointments")],
                [InlineKeyboardButton("📅 Новая запись", callback_data="book_appointment")],
                [InlineKeyboardButton("🏠 Главное меню", callback_data="back_to_main")]
            ]
            
            await query.edit_message_text(
                success_text,
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode='Markdown'
            )
        else:
            await query.edit_message_text(
                "❌ *Это время уже занято!*\n\n"
                "Пожалуйста, выберите другое время или дату.",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("📅 Выбрать дату", callback_data="book_appointment")],
                    [InlineKeyboardButton("🏠 В меню", callback_data="back_to_main")]
                ]),
                parse_mode='Markdown'
            )

async def ask_for_phone(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Запрос номера телефона"""
    query = update.callback_query
    await query.answer()
    
    await query.edit_message_text(
        "📱 *Введите ваш номер телефона для связи:*\n\n"
        "Формат: +7 XXX XXX XX XX или 8 XXX XXX XX XX\n\n"
        "Или нажмите /skip если не хотите указывать",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("◀️ Назад", callback_data="book_appointment")]
        ]),
        parse_mode='Markdown'
    )
    
    # Устанавливаем состояние ожидания телефона
    context.user_data['waiting_for_phone'] = True

async def my_appointments(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Мои записи"""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    appointments = get_user_appointments(user_id)
    
    if not appointments:
        await query.edit_message_text(
            "📭 *У вас нет активных записей*\n\n"
            "Хотите записаться на промывку мозгов? Это того стоит! 🧠✨",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔄 Записаться", callback_data="book_appointment")],
                [InlineKeyboardButton("💰 Услуги", callback_data="services_info")],
                [InlineKeyboardButton("🏠 Главное меню", callback_data="back_to_main")]
            ]),
            parse_mode='Markdown'
        )
        return
    
    appointments_text = "📋 *Ваши активные записи:*\n\n"
    
    for i, (date_str, time_str, service_code, created_at) in enumerate(appointments, 1):
        date_obj = datetime.strptime(date_str, "%Y-%m-%d")
        day_name = get_russian_day_name(date_obj.weekday())
        service_name, price = get_service_name(service_code)
        
        appointments_text += f"*{i}. {service_name}*\n"
        appointments_text += f"   📅 {date_obj.strftime('%d.%m.%Y')} ({day_name[:3]})\n"
        appointments_text += f"   ⏰ {time_str} | 💰 {price}₽\n"
        appointments_text += f"   🆔 {date_str}_{time_str}\n\n"
    
    appointments_text += "*Для отмены записи свяжитесь с администратором:* @brainwash_admin"
    
    keyboard = [
        [InlineKeyboardButton("🔄 Новая запись", callback_data="book_appointment")],
        [InlineKeyboardButton("📅 Посмотреть расписание", callback_data="view_schedule")],
        [InlineKeyboardButton("🏠 Главное меню", callback_data="back_to_main")]
    ]
    
    await query.edit_message_text(
        appointments_text,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='Markdown'
    )

async def services_info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Информация об услугах"""
    query = update.callback_query
    await query.answer()
    
    services_text = """
🧠 *УСЛУГИ И ЦЕНЫ*

*1. 🧠 СТАНДАРТНАЯ ПРОМЫВКА*
• Длительность: 60 минут
• Цена: 1 500₽
• Что входит:
  ✓ Диагностика состояния
  ✓ Базовая очистка
  ✓ Рекомендации
  ✓ Чай/кофе

*2. 🌀 ГЛУБОКАЯ ОЧИСТКА*
• Длительность: 90 минут
• Цена: 2 500₽
• Что входит:
  ✓ Полный анализ мышления
  ✓ Глубокая проработка
  ✓ Индивидуальный подход
  ✓ Поддержка 3 дня

*3. ⚡ ЭКСПРЕСС-СЕССИЯ*
• Длительность: 30 минут
• Цена: 1 000₽
• Что входит:
  ✓ Быстрая помощь
  ✓ Экстренные случаи
  ✓ Фокус на проблеме

*4. 👑 VIP КОМПЛЕКС*
• Длительность: 120 минут
• Цена: 5 000₽
• Что входит:
  ✓ Персональный специалист
  ✓ Расширенная диагностика
  ✓ Годовой план развития
  ✓ Поддержка 30 дней
  ✓ Подарочный сертификат

*📞 Запись и консультация:*
@brainwash_admin | +7 (XXX) XXX-XX-XX
    """
    
    await query.edit_message_text(
        services_text,
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🔄 Записаться", callback_data="book_appointment")],
            [InlineKeyboardButton("📅 Расписание", callback_data="view_schedule")],
            [InlineKeyboardButton("◀️ Назад", callback_data="back_to_main")]
        ]),
        parse_mode='Markdown'
    )

async def about_clinic(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """О клинике"""
    query = update.callback_query
    await query.answer()
    
    about_text = """
🏥 *О КЛИНИКЕ «BRAIN WASH»*

*Наша миссия:*
Очистить ваш разум от ненужного хлама, негативных установок и ограничивающих убеждений!

*Преимущества:*
✅ Лицензированные специалисты
✅ Современное оборудование
✅ Индивидуальный подход
✅ Конфиденциальность
✅ Гарантия результата

*Специалисты:*
• Д-р Мыслечисткин - 15 лет опыта
• Проф. Прозрений - PhD в нейронауках
• Мастер Чистосознания - восточные практики

*Результаты:*
92% клиентов отмечают улучшение мышления уже после первой процедуры!

*Часы работы:*
Пн-Пт: 9:00-21:00
Сб: 10:00-18:00
Вс: выходной
    """
    
    await query.edit_message_text(
        about_text,
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("💰 Услуги", callback_data="services_info")],
            [InlineKeyboardButton("🔄 Записаться", callback_data="book_appointment")],
            [InlineKeyboardButton("◀️ Назад", callback_data="back_to_main")]
        ]),
        parse_mode='Markdown'
    )

async def contacts(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Контакты"""
    query = update.callback_query
    await query.answer()
    
    contacts_text = """
☎️ *КОНТАКТЫ*

*📍 Адрес:*
г. Москва, ул. Мыслительная, д. 42
Бизнес-центр «Прозрение», 3 этаж, кабинет 315

*🚇 Метро:*
• «Прозрение» (выход №3)
• «Осознанность» (10 минут пешком)

*📞 Телефоны:*
• Запись: +7 (XXX) XXX-XX-XX
• Администратор: +7 (XXX) XXX-XX-XX
• Экстренная связь: +7 (XXX) XXX-XX-XX

*📧 Email:*
• Запись: appointment@brainwash.ru
• Вопросы: info@brainwash.ru
• Сотрудничество: partners@brainwash.ru

*💬 Соцсети:*
• Telegram: @brainwash_clinic
• Instagram: @brainwash.moscow
• VK: vk.com/brainwash

*🕐 Часы работы:*
Пн-Пт: 9:00-21:00
Сб: 10:00-18:00
Вс: выходной

*🚗 Парковка:*
Бесплатная парковка на территории БЦ (2 часа)
    """
    
    await query.edit_message_text(
        contacts_text,
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("📅 Записаться", callback_data="book_appointment")],
            [InlineKeyboardButton("💰 Услуги", callback_data="services_info")],
            [InlineKeyboardButton("◀️ Назад", callback_data="back_to_main")]
        ]),
        parse_mode='Markdown'
    )

async def back_to_main(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Вернуться в главное меню"""
    query = update.callback_query
    await query.answer()
    
    await query.edit_message_text(
        "🏠 *Главное меню*\n\n"
        "*Выберите действие:* ⤵️",
        reply_markup=get_main_menu(),
        parse_mode='Markdown'
    )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка текстовых сообщений"""
    if 'waiting_for_phone' in context.user_data and context.user_data['waiting_for_phone']:
        # Пользователь вводит телефон
        phone = update.message.text
        context.user_data['user_phone'] = phone
        context.user_data['waiting_for_phone'] = False
        
        await update.message.reply_text(
            f"✅ Телефон сохранен: {phone}\n\n"
            "Теперь подтвердите запись через меню.",
            reply_markup=get_main_menu()
        )
    else:
        await update.message.reply_text(
            "Используйте меню для навигации! 📱",
            reply_markup=get_main_menu()
        )

# ==================== ОСНОВНАЯ ФУНКЦИЯ ====================
def main():
    """Запуск бота"""
    logger.info("🚀 Запускаю бота...")
    
    # Инициализация БД
    init_database()
    
    # Создание приложения
    app = Application.builder().token(TOKEN).build()
    
    # Регистрация команд
    app.add_handler(CommandHandler("start", start_command))
    
    # Регистрация callback-обработчиков
    app.add_handler(CallbackQueryHandler(view_schedule, pattern="^view_schedule$"))
    app.add_handler(CallbackQueryHandler(select_date, pattern="^date_"))
    app.add_handler(CallbackQueryHandler(select_time, pattern="^time_"))
    app.add_handler(CallbackQueryHandler(confirm_booking, pattern="^(confirm_|need_call|yes_phone|no_phone)"))
    app.add_handler(CallbackQueryHandler(my_appointments, pattern="^my_appointments$"))
    app.add_handler(CallbackQueryHandler(services_info, pattern="^services_info$"))
    app.add_handler(CallbackQueryHandler(about_clinic, pattern="^about_clinic$"))
    app.add_handler(CallbackQueryHandler(contacts, pattern="^contacts$"))
    app.add_handler(CallbackQueryHandler(back_to_main, pattern="^back_to_main$"))
    
    # Для команды "Записаться" - начинаем с выбора даты
    app.add_handler(CallbackQueryHandler(view_schedule, pattern="^book_appointment$"))
    
    # Обработчик текстовых сообщений - ИСПРАВЛЕННАЯ СТРОКА!
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    logger.info("✅ Бот запущен и готов к работе!")
    logger.info("📱 Перейдите в Telegram и напишите /start")
    
    # Запуск бота
    app.run_polling()

if __name__ == "__main__":
    main()
