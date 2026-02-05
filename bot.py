import os
import logging
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

TOKEN = os.environ.get("8582048253:AAEoLzL8ISHw37W7LmllzLtLaRCe8JbuBfk")
if not TOKEN:
    logger.error("Нет токена! Установите BOT_TOKEN")
    exit(1)

# Простая база
db = {"slots": {}}

def generate_slots():
    today = datetime.now()
    slots = {}
    for day in range(1, 8):
        date = today + timedelta(days=day)
        date_str = date.strftime("%Y-%m-%d")
        for hour in range(10, 19, 2):
            time_str = f"{hour}:00"
            key = f"{date_str}_{time_str}"
            slots[key] = {
                "date": date_str,
                "time": time_str,
                "available": True,
                "user": None
            }
    return slots

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("📅 Свободные окна", callback_data="view_slots")],
        [InlineKeyboardButton("ℹ️ Инфо", callback_data="info")]
    ]
    await update.message.reply_text(
        "👋 Бот записи на промывку мозгов!\nВыберите:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def view_slots(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    db["slots"] = generate_slots()
    available = [s for s in db["slots"].values() if s["available"]]
    
    if not available:
        await query.edit_message_text("Нет свободных окон 😔")
        return
    
    text = "📅 *Свободные окна:*\n\n"
    for slot in available[:10]:
        date = datetime.strptime(slot["date"], "%Y-%m-%d")
        text += f"• {date.strftime('%d.%m')} в {slot['time']}\n"
    
    keyboard = []
    for slot in available[:3]:
        btn_text = f"{slot['date']} {slot['time']}"
        keyboard.append([InlineKeyboardButton(btn_text, callback_data=f"book_{slot['date']}_{slot['time']}")])
    
    keyboard.append([InlineKeyboardButton("◀️ Назад", callback_data="back")])
    
    await query.edit_message_text(
        text + f"\nВсего: {len(available)} окон",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )

async def book_slot(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    data = query.data.replace("book_", "")
    date_str, time_str = data.split("_", 1)
    key = f"{date_str}_{time_str}"
    
    if key in db["slots"] and db["slots"][key]["available"]:
        db["slots"][key]["available"] = False
        db["slots"][key]["user"] = query.from_user.full_name
        
        date = datetime.strptime(date_str, "%Y-%m-%d")
        await query.edit_message_text(
            f"✅ Запись оформлена!\n\n"
            f"📅 {date.strftime('%d.%m.%Y')}\n"
            f"⏰ {time_str}\n\n"
            f"Ждем вас! 🧠",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("📅 Еще запись", callback_data="view_slots")]
            ])
        )
    else:
        await query.edit_message_text("Окно уже занято!")

async def info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    info_text = """
🧠 *Промывка мозгов*

*Услуги:*
• Стандартная (60 мин) - 1500₽
• Глубокая (90 мин) - 2500₽
• Экспресс (30 мин) - 1000₽

📍 Адрес: ул. Мыслительная, 42
📞 Телефон: +7 (XXX) XXX-XX-XX
⏰ Часы: 10:00-20:00
    """
    
    await query.edit_message_text(
        info_text,
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("📅 Записаться", callback_data="view_slots")],
            [InlineKeyboardButton("◀️ Назад", callback_data="back")]
        ]),
        parse_mode="Markdown"
    )

async def back(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    keyboard = [
        [InlineKeyboardButton("📅 Свободные окна", callback_data="view_slots")],
        [InlineKeyboardButton("ℹ️ Инфо", callback_data="info")]
    ]
    
    await query.edit_message_text(
        "🏠 *Главное меню*\n\nВыберите действие:",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )

def main():
    app = Application.builder().token(TOKEN).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(view_slots, pattern="^view_slots$"))
    app.add_handler(CallbackQueryHandler(book_slot, pattern="^book_"))
    app.add_handler(CallbackQueryHandler(info, pattern="^info$"))
    app.add_handler(CallbackQueryHandler(back, pattern="^back$"))
    
    logger.info("Бот запущен!")
    app.run_polling()

if __name__ == "__main__":
    main()
