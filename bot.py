# pyright: reportOptionalMemberAccess=false, reportOptionalSubscript=false, reportAssignmentType=false
import os
import json
import logging
import requests
import feedparser
from deep_translator import GoogleTranslator
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes

# Настройка
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

BOT_TOKEN = "7980284387:AAHBd1L_j0d3aIHrlXp47KkzZnZP5DvPIhs"
CHANNEL_ID = -1001785313081
HISTORY_FILE = os.path.join(os.path.dirname(__file__), "posted_ru.json")
GEMINI_API_KEY = "AIzaSyAAduHqs32MSc-S7DF1M30DECiDwi3JXzc"
GEMINI_URL = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={GEMINI_API_KEY}"

CATEGORIES = {
    "top": ("🔥 Главные", "https://www.sciencedaily.com/rss/top_news.xml"),
    "health": ("🧬 Здоровье", "https://www.sciencedaily.com/rss/health_medicine.xml"),
    "space": ("🚀 Космос", "https://www.sciencedaily.com/rss/space_time.xml"),
    "computers": ("💻 IT", "https://www.sciencedaily.com/rss/computers_math.xml"),
    "matter": ("⚛️ Физика", "https://www.sciencedaily.com/rss/matter_energy.xml"),
    "environment": ("🌍 Экология", "https://www.sciencedaily.com/rss/earth_climate.xml"),
    "society": ("🧠 Общество", "https://www.sciencedaily.com/rss/society_education.xml"),
}


# ФУНКЦИЯ ПЕРЕВОДА (СТРАХОВКА)
def force_translate(text: str) -> str:
    try:
        # Простой перевод на русский
        return GoogleTranslator(source='auto', target='ru').translate(text)
    except:
        return text

# ОСНОВНАЯ ГЕНЕРАЦИЯ
def gemini_magic(title: str, summary: str, link: str) -> str:
    # 1. Сначала переводим входные данные на русский
    ru_title = GoogleTranslator(source='en', target='ru').translate(title)
    ru_summary = GoogleTranslator(source='en', target='ru').translate(summary)
    
    # 2. Теперь просим Gemini работать с уже готовым русским текстом
    prompt = f"Напиши виральный пост для Telegram на русском языке. Используй эмодзи и жирный шрифт. Тема: {ru_title}. Описание: {ru_summary}. Ссылка: {link}"
    
    try:
        r = requests.post(GEMINI_URL, json={"contents": [{"role": "user", "parts": [{"text": prompt}]}]}, timeout=30)
        return r.json()["candidates"][0]["content"]["parts"][0]["text"]
    except Exception as e:
        logger.error(f"Gemini error: {e}")
        return f"**{ru_title}**\n\n{ru_summary}\n\nИсточник: {link}"

def load_history():
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE, "r", encoding="utf-8") as f: return set(json.load(f))
        except: return set()
    return set()

def save_history(h):
    with open(HISTORY_FILE, "w", encoding="utf-8") as f: json.dump(list(h), f, ensure_ascii=False)

# ================== БОТ ==================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    kb = [[InlineKeyboardButton(name, callback_data=f"cat|{key}")] for key, (name, _) in CATEGORIES.items()]
    await context.bot.send_message(update.effective_chat.id, "Привет! Выбери категорию:", reply_markup=InlineKeyboardMarkup(kb))

async def show_article(query, context, idx: int):
    candidates = context.user_data.get("candidates") or []
    if not candidates or idx >= len(candidates):
        await context.bot.send_message(query.message.chat.id, "Всё просмотрено.")
        return
    
    art = candidates[idx]
    text = gemini_magic(art["title"], art["summary"], art["link"])
    
    kb = [[InlineKeyboardButton("✅ Опубликовать", callback_data=f"post|{idx}")],
          [InlineKeyboardButton("⏩ След.", callback_data=f"next|{idx+1}")]]
    
    await context.bot.send_message(query.message.chat.id, f"ПРЕДПРОСМОТР:\n\n{text}", parse_mode="HTML", reply_markup=InlineKeyboardMarkup(kb))

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    if not q or not q.data: return
    await q.answer()
    
    if q.data.startswith("cat|"):
        key = q.data.split("|")[1]
        feed = feedparser.parse(CATEGORIES[key][1])
        history = load_history()
        candidates = [{"title": e.title, "link": e.link, "summary": e.summary} for e in feed.entries if e.link not in history][:5]
        
        if not candidates:
            await context.bot.send_message(q.message.chat.id, "Новых статей нет.")
            return
        context.user_data["candidates"] = candidates
        await show_article(q, context, 0)

    elif q.data.startswith("post|"):
        idx = int(q.data.split("|")[1])
        art = context.user_data["candidates"][idx]
        text = gemini_magic(art["title"], art["summary"], art["link"])
        await context.bot.send_message(CHANNEL_ID, text, parse_mode="HTML")
        
        h = load_history()
        h.add(art["link"])
        save_history(h)
        await context.bot.send_message(q.message.chat.id, "Улетело в канал! 🔥")

    elif q.data.startswith("next|"):
        await show_article(q, context, int(q.data.split("|")[1]))

def main():
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button_handler))
    print("Бот запущен...")
    app.run_polling()

if __name__ == "__main__":
    main()