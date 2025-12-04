# app.py - FastAPI + Telegram Bot (Bitta fayl)
import os
import asyncio
import sqlite3
import random
from datetime import datetime
from typing import List, Optional
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import uvicorn

from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

# ==================== SOZLAMALAR ====================
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "DEFAULT_TOKEN")
SECRET_PASSWORD = os.getenv("SECRET_PASSWORD", "12345")  # Parol
DB_NAME = "notes.db"
FASTAPI_PORT = 8000

# ==================== DATABASE ====================
def init_db():
    """Database yaratish"""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS notes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            question TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            color TEXT DEFAULT 'color-yellow',
            telegram_user_id INTEGER,
            telegram_username TEXT
        )
    """)
    conn.commit()
    conn.close()
    print("✅ Database tayyor!")

def get_db():
    """Database connection"""
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn

def get_random_color():
    """Tasodifiy rang"""
    colors = ['color-yellow', 'color-pink', 'color-cyan', 'color-orange',
              'color-blue', 'color-green', 'color-lavender', 'color-peach']
    return random.choice(colors)

# ==================== PYDANTIC MODELS ====================
class NoteCreate(BaseModel):
    question: str
    telegram_user_id: Optional[int] = None
    telegram_username: Optional[str] = None

class NoteResponse(BaseModel):
    id: int
    question: str
    created_at: str
    color: str
    telegram_user_id: Optional[int] = None
    telegram_username: Optional[str] = None

class PasswordCheck(BaseModel):
    password: str

# ==================== TELEGRAM BOT ====================
telegram_app = None

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Bot /start komandasi"""
    await update.message.reply_text(
        "👋 Salom! Men Post-it Notes botiman.\n\n"
        "📝 Menga har qanday savol yuboring, men uni saqlayaman.\n"
        "🌐 Barcha savollarni web sahifada ko'rishingiz mumkin.\n\n"
        "Komandalar:\n"
        "/start - Botni boshlash\n"
        "/help - Yordam\n"
        "/stats - Statistika"
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Bot /help komandasi"""
    await update.message.reply_text(
        "ℹ️ Qanday foydalanish:\n\n"
        "1️⃣ Menga har qanday savol yuboring\n"
        "2️⃣ Men uni saqlayman\n"
        "3️⃣ Web sahifada barcha savollar ko'rinadi\n\n"
        "💡 Misol: 'Qanday qilib Python o'rganish kerak?'\n\n"
        f"🌐 Web: http://localhost:{FASTAPI_PORT}"
    )

async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Statistika ko'rsatish"""
    try:
        conn = get_db()
        cursor = conn.cursor()
        
        cursor.execute("SELECT COUNT(*) as total FROM notes")
        total = cursor.fetchone()['total']
        
        cursor.execute("""
            SELECT COUNT(DISTINCT telegram_user_id) as users 
            FROM notes 
            WHERE telegram_user_id IS NOT NULL
        """)
        users = cursor.fetchone()['users']
        
        conn.close()
        
        await update.message.reply_text(
            f"📊 Statistika:\n\n"
            f"📝 Jami savollar: {total}\n"
            f"👥 Foydalanuvchilar: {users}\n"
            f"⏰ Vaqt: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        )
    except Exception as e:
        print(f"Stats xatolik: {e}")
        await update.message.reply_text("❌ Statistika olishda xatolik")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Foydalanuvchi xabarini qabul qilish"""
    user = update.effective_user
    question = update.message.text
    
    try:
        conn = get_db()
        cursor = conn.cursor()
        
        color = get_random_color()
        
        cursor.execute("""
            INSERT INTO notes (question, color, telegram_user_id, telegram_username)
            VALUES (?, ?, ?, ?)
        """, (question, color, user.id, user.username or user.first_name))
        
        conn.commit()
        note_id = cursor.lastrowid
        conn.close()
        
        await update.message.reply_text(
            f"✅ Savolingiz saqlandi! (ID: {note_id})\n"
            f"🌐 Web sahifada ko'rishingiz mumkin."
        )
    except Exception as e:
        print(f"Xatolik: {e}")
        await update.message.reply_text(
            "❌ Saqlashda xatolik yuz berdi.\n"
            "Iltimos, qaytadan urinib ko'ring."
        )

async def start_telegram_bot():
    """Telegram botni ishga tushirish"""
    global telegram_app
    
    print("🤖 Telegram bot ishga tushmoqda...")
    
    telegram_app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
    
    # Komandalar
    telegram_app.add_handler(CommandHandler("start", start_command))
    telegram_app.add_handler(CommandHandler("help", help_command))
    telegram_app.add_handler(CommandHandler("stats", stats_command))
    telegram_app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    # Botni ishga tushirish
    await telegram_app.initialize()
    await telegram_app.start()
    await telegram_app.updater.start_polling(allowed_updates=Update.ALL_TYPES)
    
    print("✅ Telegram bot tayyor!")

async def stop_telegram_bot():
    """Telegram botni to'xtatish"""
    global telegram_app
    if telegram_app:
        await telegram_app.updater.stop()
        await telegram_app.stop()
        await telegram_app.shutdown()
        print("🛑 Telegram bot to'xtatildi")

# ==================== FASTAPI ====================
@asynccontextmanager
async def lifespan(app: FastAPI):
    """FastAPI lifecycle - bot'ni boshlash/to'xtatish"""
    # Startup
    init_db()
    await start_telegram_bot()
    yield
    # Shutdown
    await stop_telegram_bot()

app = FastAPI(
    title="Post-it Notes API",
    description="FastAPI + Telegram Bot",
    lifespan=lifespan
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ==================== API ENDPOINTS ====================

@app.get("/")
async def root():
    """API ma'lumoti"""
    return {
        "message": "Post-it Notes API + Telegram Bot",
        "status": "running",
        "telegram_bot": "active" if telegram_app else "inactive"
    }

@app.get("/health")
async def health():
    """Server holati"""
    return {
        "status": "ok",
        "timestamp": datetime.now().isoformat(),
        "telegram_bot": "active" if telegram_app else "inactive"
    }

@app.post("/api/check-password")
async def check_password(data: PasswordCheck):
    """Paroli tekshirish"""
    if data.password == SECRET_PASSWORD:
        return {"authorized": True, "message": "Parol to'g'ri"}
    else:
        raise HTTPException(status_code=401, detail="Parol noto'g'ri")

@app.get("/api/notes", response_model=List[NoteResponse])
async def get_notes(password: str = None):
    """Paroli tekshirib savollarni olish"""
    if password != SECRET_PASSWORD:
        raise HTTPException(status_code=401, detail="Parol talab qilinadi yoki noto'g'ri")
    
    try:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, question, created_at, color, telegram_user_id, telegram_username
            FROM notes
            ORDER BY created_at DESC
        """)
        notes = cursor.fetchall()
        conn.close()
        
        return [dict(note) for note in notes]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/notes", response_model=NoteResponse)
async def create_note(note: NoteCreate):
    """Yangi savol qo'shish"""
    try:
        conn = get_db()
        cursor = conn.cursor()
        
        color = get_random_color()
        
        cursor.execute("""
            INSERT INTO notes (question, color, telegram_user_id, telegram_username)
            VALUES (?, ?, ?, ?)
        """, (note.question, color, note.telegram_user_id, note.telegram_username))
        
        conn.commit()
        note_id = cursor.lastrowid
        
        cursor.execute("SELECT * FROM notes WHERE id = ?", (note_id,))
        new_note = cursor.fetchone()
        conn.close()
        
        return dict(new_note)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/api/notes/{note_id}")
async def delete_note(note_id: int, password: str = None):
    """Savolni o'chirish (parol talab)"""
    if password != SECRET_PASSWORD:
        raise HTTPException(status_code=401, detail="Parol talab qilinadi yoki noto'g'ri")
    
    try:
        conn = get_db()
        cursor = conn.cursor()
        
        cursor.execute("SELECT * FROM notes WHERE id = ?", (note_id,))
        note = cursor.fetchone()
        
        if not note:
            raise HTTPException(status_code=404, detail="Savol topilmadi")
        
        cursor.execute("DELETE FROM notes WHERE id = ?", (note_id,))
        conn.commit()
        conn.close()
        
        return {"message": "Savol o'chirildi", "id": note_id}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/stats")
async def get_stats(password: str = None):
    """Statistika (parol talab)"""
    if password != SECRET_PASSWORD:
        raise HTTPException(status_code=401, detail="Parol talab qilinadi yoki noto'g'ri")
    
    try:
        conn = get_db()
        cursor = conn.cursor()
        
        cursor.execute("SELECT COUNT(*) as total FROM notes")
        total = cursor.fetchone()['total']
        
        cursor.execute("""
            SELECT COUNT(DISTINCT telegram_user_id) as users 
            FROM notes 
            WHERE telegram_user_id IS NOT NULL
        """)
        users = cursor.fetchone()['users']
        
        cursor.execute("""
            SELECT created_at FROM notes 
            ORDER BY created_at DESC LIMIT 1
        """)
        last = cursor.fetchone()
        last_note = dict(last)['created_at'] if last else None
        
        conn.close()
        
        return {
            "total_notes": total,
            "total_users": users,
            "last_note": last_note,
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ==================== MAIN ====================
if __name__ == "__main__":
    print("=" * 60)
    print("🚀 POST-IT NOTES - FastAPI + Telegram Bot")
    print("=" * 60)
    print(f"📝 API: http://localhost:{FASTAPI_PORT}")
    print(f"📚 Docs: http://localhost:{FASTAPI_PORT}/docs")
    print(f"🤖 Telegram Bot: Ishga tushmoqda...")
    print(f"🔐 Parol: {SECRET_PASSWORD}")
    print("=" * 60)
    print("\n⚠️  MUHIM: TELEGRAM_BOT_TOKEN'ni o'zgartiring!\n")
    
    # Serverni ishga tushirish
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=FASTAPI_PORT,
        log_level="info"
    )