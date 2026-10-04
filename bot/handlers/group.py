import os
import json
import asyncio
import re
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from sqlmodel import Session, select
from database import engine
from models import User

GROUP_ID = os.getenv("GROUP_CHAT_ID")
BOT_USERNAME = os.getenv("BOT_USERNAME", "PalembangPyBOT")

TOPICS_FILE = "threads.json"
topicList = {}

# --- Load & Save Topics Safely ---
try:
    if os.path.exists(TOPICS_FILE):
        with open(TOPICS_FILE, "r") as f:
            topicList = json.load(f)
    else:
        topicList = {}
        with open(TOPICS_FILE, "w") as f:
            json.dump(topicList, f, indent=2)
except Exception:
    topicList = {}

def save_topic_list():
    try:
        with open(TOPICS_FILE, "w") as f:
            json.dump(topicList, f, indent=2)
    except Exception:
        pass

ALLOWED_TOPIC_NAMES = ["Compiler", "Playground", "Playground Python"]

def is_topic_allowed(thread_id):
    if not thread_id:
        return True  # Jika di General / non-forum, biarkan
    id_str = str(thread_id)
    topic = topicList.get(id_str)
    # Jika topik belum terdaftar, izinkan dulu sambil dideteksi, atau batasi sesuai kebijakan
    if not topic:
        return True 
    return topic["name"] in ALLOWED_TOPIC_NAMES

def scan_and_save_topic(update: Update):
    if not update.message:
        return None
    
    thread_id = update.message.message_thread_id
    if not thread_id:
        return None

    id_str = str(thread_id)
    if topicList.get(id_str):
        return topicList[id_str]

    # Ambil nama topik langsung dari event forum_topic_created
    topic_name = None
    if update.message.forum_topic_created:
        topic_name = update.message.forum_topic_created.name
    elif update.message.reply_to_message and update.message.reply_to_message.forum_topic_created:
        topic_name = update.message.reply_to_message.forum_topic_created.name

    if not topic_name:
        return None

    topicList[id_str] = {
        "name": topic_name,
        "chatId": str(update.effective_chat.id),
        "lastSeen": datetime.utcnow().isoformat()
    }
    save_topic_list()
    return topicList[id_str]

pendingKickTimers = {}

async def handle_member_join(update: Update, context: ContextTypes.DEFAULT_TYPE):
    new_members = update.message.new_chat_members if update.message else []

    for user in new_members:
        if user.is_bot:
            continue

        userId = str(user.id)
        rawUserId = user.id
        name = user.first_name or "Teman"

        # Proteksi Akun Hapus / Ghost Account
        if user.first_name == "Deleted Account":
            try:
                await context.bot.ban_chat_member(update.effective_chat.id, rawUserId)
                await context.bot.unban_chat_member(update.effective_chat.id, rawUserId)
            except Exception:
                pass
            continue

        with Session(engine) as db:
            member_data = db.exec(select(User).where(User.telegram_id == userId, User.deleted_at == None)).first()

        if not member_data:
            keyboard = InlineKeyboardMarkup([[
                InlineKeyboardButton("📝 Daftar via DM Bot", url=f"https://t.me/{BOT_USERNAME}?start=register")
            ]])

            gateMsg = await update.message.reply_text(
                f"Halo {name}!\n\n"
                f"⚠️ Kamu *belum terdaftar* di database PalembangPy.\n"
                f"Silakan daftar via DM Bot dalam waktu *3 menit*, atau kamu akan dikeluarkan otomatis dari grup.",
                parse_mode="Markdown",
                reply_markup=keyboard
            )

            async def kick_task():
                await asyncio.sleep(180)
                try:
                    with Session(engine) as db:
                        reCheck = db.exec(select(User).where(User.telegram_id == userId, User.deleted_at == None)).first()
                    if not reCheck:
                        await context.bot.ban_chat_member(update.effective_chat.id, rawUserId)
                        await context.bot.unban_chat_member(update.effective_chat.id, rawUserId)
                        await context.bot.delete_message(update.effective_chat.id, gateMsg.message_id)
                except Exception:
                    pass
                finally:
                    pendingKickTimers.pop(userId, None)

            task = asyncio.create_task(kick_task())
            pendingKickTimers[userId] = task
            continue

        welcomeMsg = await update.message.reply_text(
            f"Selamat datang, {name}!\n\n"
            f"Senang kamu bergabung di grup PalembangPy.\n"
            f"Kode Member: `{member_data.member_code or '-'}`\n"
            f"Semoga aktif berbagi & belajar bersama ya!",
            parse_mode="Markdown"
        )

        async def delete_welcome():
            await asyncio.sleep(15)
            try:
                await context.bot.delete_message(update.effective_chat.id, welcomeMsg.message_id)
            except Exception:
                pass
        asyncio.create_task(delete_welcome())

        with Session(engine) as db:
            member_data.points += 5
            db.add(member_data)
            db.commit()

async def handle_member_leave(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.message.left_chat_member if update.message else None
    if not user or user.is_bot:
        return

    userId = str(user.id)
    if userId in pendingKickTimers:
        pendingKickTimers[userId].cancel()
        pendingKickTimers.pop(userId, None)

    name = user.first_name or "Teman"
    leaveMsg = await update.message.reply_text(
        f"Sampai jumpa, {name}...\n"
        f"Terima kasih sudah pernah bergabung di PalembangPy.\n"
        f"Kapan-kapan kembali lagi ya!"
    )

    async def delete_leave():
        await asyncio.sleep(10)
        try:
            await context.bot.delete_message(update.effective_chat.id, leaveMsg.message_id)
        except Exception:
            pass
    asyncio.create_task(delete_leave())

async def track_activity(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.effective_chat:
        return

    # Pastikan hanya memantau grup utama yang dikonfigurasi
    if GROUP_ID and str(update.effective_chat.id) != str(GROUP_ID):
        return

    scan_and_save_topic(update)
    thread_id = update.message.message_thread_id if update.message else None

    # 1. Enforce Topic Restriction (jika topik tidak diizinkan, hapus pesan)
    if thread_id and not is_topic_allowed(thread_id):
        try:
            await update.message.delete()
            return
        except Exception:
            pass

    # 2. Deteksi Akun Hapus / Spam Userbot
    if update.effective_user and update.effective_user.first_name == "Deleted Account":
        try:
            if update.message:
                await update.message.delete()
            await context.bot.ban_chat_member(update.effective_chat.id, update.effective_user.id)
            await context.bot.unban_chat_member(update.effective_chat.id, update.effective_user.id)
            return
        except Exception:
            pass

    # 3. Double-Check Unregistered User (Mencegah lolos jika bot restart)
    if update.effective_user and not update.effective_user.is_bot:
        userId = str(update.effective_user.id)
        with Session(engine) as db:
            member_data = db.exec(select(User).where(User.telegram_id == userId, User.deleted_at == None)).first()
        
        if not member_data:
            # Jika ngotot chat tapi belum daftar dan tidak ada di timer, langsung kick
            try:
                if update.message:
                    await update.message.delete()
                await context.bot.ban_chat_member(update.effective_chat.id, update.effective_user.id)
                await context.bot.unban_chat_member(update.effective_chat.id, update.effective_user.id)
            except Exception:
                pass
            return

    # 4. Filter Spam & Judol Ketat (Menggunakan regex keyword dan link luar)
    if update.message and update.message.text:
        text = update.message.text.lower()
        spam_keywords = ["slot", "judol", "gacor", "crypto", "investasi bodong", "maxwin", "pragmatic"]
        has_spam_keyword = any(kw in text for kw in spam_keywords)
        
        # Deteksi link eksternal yang bukan t.me/palembangpy atau domain sah komunitas
        has_unauthorized_link = "t.me/" in text and "palembangpy" not in text
        has_http_link = bool(re.search(r"https?://(?!t\.me/palembangpy)\S+", text))

        if (has_spam_keyword or has_unauthorized_link or has_http_link) and update.effective_user and not update.effective_user.is_bot:
            # Pengecualian jika admin yang mengirim (opsional, tapi aman)
            try:
                member_status = await context.bot.get_chat_member(update.effective_chat.id, update.effective_user.id)
                if member_status.status in ["creator", "administrator"]:
                    pass  # Biarkan jika admin
                else:
                    await update.message.delete()
                    await context.bot.ban_chat_member(update.effective_chat.id, update.effective_user.id)
                    
                    username_label = f"@{update.effective_user.username}" if update.effective_user.username else update.effective_user.first_name
                    warn = await update.message.reply_text(f"⛔ {username_label} telah dibanned permanen karena terindikasi Spam/Judol/Link ilegal.")
                    
                    # Perbaikan bug rekursi: Hapus pesan peringatan setelah 5 detik tanpa infinite loop
                    async def delete_warn_task(chat_id, msg_id):
                        await asyncio.sleep(5)
                        try:
                            await context.bot.delete_message(chat_id, msg_id)
                        except Exception:
                            pass
                    
                    asyncio.create_task(delete_warn_task(update.effective_chat.id, warn.message_id))
                    return
            except Exception:
                pass

    # 5. Reward Poin Keaktifan
    if update.effective_user and not update.effective_user.is_bot:
        userId = str(update.effective_user.id)
        with Session(engine) as db:
            member_data = db.exec(select(User).where(User.telegram_id == userId, User.deleted_at == None)).first()
            if member_data:
                member_data.points += 1
                db.add(member_data)
                db.commit()

async def invite_to_group(context: ContextTypes.DEFAULT_TYPE, userId):
    try:
        strUserId = str(userId)
        if strUserId in pendingKickTimers:
            pendingKickTimers[strUserId].cancel()
            pendingKickTimers.pop(strUserId, None)

        await context.bot.unban_chat_member(GROUP_ID, userId)
        link = await context.bot.export_chat_invite_link(GROUP_ID)
        return link
    except Exception:
        return None
