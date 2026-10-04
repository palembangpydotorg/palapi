import os
from telegram import Update, ReplyKeyboardRemove, InlineKeyboardButton, InlineKeyboardMarkup, InputFile
from telegram.ext import (
    ContextTypes,
    ConversationHandler,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    filters,
)
from sqlmodel import Session, select
from database import engine
from models import User
from crud import create_user
from bot.captcha import generate_captcha_gif

ASK_NAME, ASK_CAPTCHA, CONFIRM = range(3)


async def start_register(update: Update, context: ContextTypes.DEFAULT_TYPE):
    tg_user = update.effective_user
    
    with Session(engine) as db:
        existing = db.exec(
            select(User).where(User.telegram_id == str(tg_user.id), User.deleted_at == None)
        ).first()
        
        if existing:
            await update.message.reply_text(
                f"Halo {existing.name}! Kamu sudah terdaftar sebagai member PalembangPy."
            )
            return ConversationHandler.END

    await update.message.reply_text(
        "👋 Selamat datang di PalembangPy!\n\n"
        "Mari buat kartu member komunitasmu. Siapa nama lengkapmu?"
    )
    return ASK_NAME


async def get_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["name"] = update.message.text.strip().lower()
    
    loading_msg = await update.message.reply_text("⚙️ Sedang merender Captcha jam interaktif dengan Manim... Harap tunggu sebentar.")
    
    gif_path = f"/tmp/captcha_{update.effective_user.id}.gif"
    try:
        generate_captcha_gif(gif_path)
        
        with open("/tmp/captcha_ans.txt", "r") as f:
            context.user_data["captcha_ans"] = f.read().strip()
            
        with open(gif_path, "rb") as gif_file:
            await update.message.reply_animation(
                animation=InputFile(gif_file),
                caption="🤖 *Verifikasi Keamanan Captcha*\n\nPerhatikan animasi jam di atas, lalu balas pesan ini dengan angka yang ditunjuk oleh jarum!",
                parse_mode="Markdown"
            )
        await loading_msg.delete()
    except Exception as e:
        await loading_msg.edit_text(f"Gagal merender captcha: {str(e)}")
        return ConversationHandler.END
    finally:
        if os.path.exists(gif_path):
            os.remove(gif_path)

    return ASK_CAPTCHA


async def get_captcha(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_answer = update.message.text.strip()
    correct_answer = context.user_data.get("captcha_ans")
    
    if user_answer != correct_answer:
        await update.message.reply_text(
            "❌ Jawaban Captcha kamu salah! Silakan balas lagi dengan angka yang benar sesuai jarum jam."
        )
        return ASK_CAPTCHA
        
    tg_user = update.effective_user
    name = context.user_data.get("name")
    
    avatar_url = None
    photos = await tg_user.get_profile_photos(limit=1)
    if photos.total_count > 0:
        file_id = photos.photos[0][-1].file_id
        file_obj = await context.bot.get_file(file_id)
        avatar_url = file_obj.file_path
        
    context.user_data["avatar_url"] = avatar_url
    
    card_text = (
        "📋 *Konfirmasi Data Pendaftaran*\n\n"
        f"👤 Nama: `{name}`\n"
        f"🌐 Username: `@{tg_user.username or '-'}`\n"
        f"🆔 Telegram ID: `{tg_user.id}`\n\n"
        "Pastikan data di atas sudah benar. Klik tombol di bawah untuk menyelesaikan pendaftaran."
    )
    
    keyboard = [
        [
            InlineKeyboardButton("✅ Konfirmasi & Daftar", callback_data="confirm_reg"),
            InlineKeyboardButton("❌ Batal", callback_data="cancel_reg")
        ]
    ]
    
    await update.message.reply_text(
        card_text, 
        parse_mode="Markdown", 
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    return CONFIRM


async def confirm_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if query.data == "cancel_reg":
        await query.edit_message_text("Pendaftaran dibatalkan.")
        return ConversationHandler.END
        
    if query.data == "confirm_reg":
        tg_user = query.from_user
        name = context.user_data.get("name")
        avatar_url = context.user_data.get("avatar_url")
        
        with Session(engine) as db:
            try:
                user_in = {
                    "name": name,
                    "username": tg_user.username,
                    "telegram_id": str(tg_user.id),
                    "avatar_url": avatar_url,
                    "bio": None,
                    "is_admin": False,
                    "is_staff": False,
                    "points": 0,
                }
                
                user, plain_password = create_user(db, user_in)
                
                await query.edit_message_text(
                    f"✅ *Pendaftaran Berhasil Disimpan!*\n\n"
                    f"👤 Nama: {user.name}\n"
                    f"💳 Member Code: `{user.member_code}`\n"
                    f"🔑 Password Default: `{plain_password}`\n\n"
                    f"Simpan password di atas untuk login ke website PalembangPy. Gunakan /setbio untuk melengkapi profilmu nanti.",
                    parse_mode="Markdown",
                )
            except Exception as e:
                await query.edit_message_text(
                    f"❌ Terjadi kesalahan saat menyimpan ke database: {str(e)}"
                )
                
        return ConversationHandler.END


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Pendaftaran dibatalkan.", 
        reply_markup=ReplyKeyboardRemove()
    )
    return ConversationHandler.END

# Export ConversationHandler
register_conv = ConversationHandler(
    entry_points=[CommandHandler("register", start_register)],
    states={
        ASK_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_name)],
        ASK_CAPTCHA: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_captcha)],
        CONFIRM: [CallbackQueryHandler(confirm_callback, pattern="^(confirm_reg|cancel_reg)$")],
    },
    fallbacks=[CommandHandler("cancel", cancel)],
)
