from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes

sesi = {}

async def clear_history(update: Update, context: ContextTypes.DEFAULT_TYPE, message_id_list: list):
    for msg_id in message_id_list:
        try:
            await context.bot.delete_message(chat_id=update.effective_chat.id, message_id=msg_id)
        except Exception as e:
            print(f"Gagal hapus pesan: {e}")

async def show_main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE, user_id: int):
    keyboard = [
        [
            InlineKeyboardButton("Buat Akun", callback_data="buat_akun"),
            InlineKeyboardButton("Tentang", callback_data="tentang")
        ],
        [
            InlineKeyboardButton("Menu", callback_data="menu_utama")
        ],
        [
            InlineKeyboardButton("Ikuti Kami", url="https://instagram.com/palembangpy"),
            InlineKeyboardButton("Beri Dukungan", url="https://sociabuzz.com/palembangpy/tribe")
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    text = (
        "Selamat Datang di PalembangPy!\n"
        "Komunitas Pengembang Python Kota Palembang\n\n"
        "Belajar, Berbagi, dan Berkembang Bersama.\n"
        "Silakan pilih menu di bawah"
    )

    if update.message:
        message = await update.message.reply_text(text, reply_markup=reply_markup)
    elif update.callback_query:
        message = await update.callback_query.message.reply_text(text, reply_markup=reply_markup)
    else:
        return

    sesi[user_id] = {"message_list": [message.message_id]}

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    await show_main_menu(update, context, user_id)

async def handle_start_callbacks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    data = query.data
    if data == "tentang":
        await query.message.reply_text("PalembangPy adalah komunitas pengembang Python di Palembang yang berfokus pada kolaborasi dan berbagi ilmu.")
    elif data == "menu_utama":
        await show_main_menu(update, context, update.effective_user.id)
    # Catatan: "buat_akun" tidak perlu dihandle di sini karena sudah ditangani oleh register_conv
