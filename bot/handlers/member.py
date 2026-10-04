from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes
from sqlmodel import Session, select, desc
from database import engine
from models import User, Event, Project

async def show_general_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [
            InlineKeyboardButton("👤 Profil Saya", callback_data="member_profile"),
            InlineKeyboardButton("📅 Event Komunitas", callback_data="member_events")
        ],
        [
            InlineKeyboardButton("🚀 Project Komunitas", callback_data="member_projects"),
            InlineKeyboardButton("🏆 Leaderboard Poin", callback_data="member_leaderboard")
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    text = "*🌟 Menu Utama PalembangPy*\n\nPilih menu yang ingin kamu akses:"

    if update.callback_query:
        await update.callback_query.answer()
        await update.callback_query.edit_message_text(text, parse_mode="Markdown", reply_markup=reply_markup)
    else:
        await update.message.reply_text(text, parse_mode="Markdown", reply_markup=reply_markup)

async def handle_member_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    back_kb = InlineKeyboardMarkup([[InlineKeyboardButton("← Kembali ke Menu", callback_data="member_menu")]])

    if data == "member_menu":
        await show_general_menu(update, context)

    elif data == "member_profile":
        tg_id = str(query.from_user.id)
        with Session(engine) as db:
            user = db.exec(select(User).where(User.telegram_id == tg_id, User.deleted_at == None)).first()
            if not user:
                text = "❌ Akun kamu belum terdaftar di database. Silakan daftar terlebih dahulu melalui grup atau perintah `/start`."
            else:
                role = "Super Admin 👑" if user.is_admin else ("Staff 🧑‍💼" if user.is_staff else "Member 🌟")
                text = (
                    f"*👤 Profil Anggota*\n\n"
                    f"Nama: *{user.name}*\n"
                    f"Username: `@{user.username}`\n"
                    f"Kode Member: `{user.member_code}`\n"
                    f"Role: *{role}*\n"
                    f"Poin Keaktifan: *{user.points or 0}* pts"
                )
        await query.edit_message_text(text, parse_mode="Markdown", reply_markup=back_kb)

    elif data == "member_events":
        with Session(engine) as db:
            events = db.exec(select(Event).where(Event.deleted_at == None).limit(5)).all()
            list_str = "\n\n".join([f"📅 *{e.title}*\nLokasi: {e.location or 'Online'}" for e in events]) or "Belum ada event terdekat."
            text = f"*📅 Event Komunitas PalembangPy:*\n\n{list_str}"
        await query.edit_message_text(text, parse_mode="Markdown", reply_markup=back_kb)

    elif data == "member_projects":
        with Session(engine) as db:
            projects = db.exec(select(Project).where(Project.status == "published", Project.deleted_at == None).limit(5)).all()
            list_str = "\n\n".join([f"🚀 *{p.title}*\n{p.description or '-'}" for p in projects]) or "Belum ada project yang dipublikasikan."
            text = f"*📁 Project Anggota PalembangPy:*\n\n{list_str}"
        await query.edit_message_text(text, parse_mode="Markdown", reply_markup=back_kb)

    elif data == "member_leaderboard":
        with Session(engine) as db:
            top_users = db.exec(select(User).where(User.deleted_at == None).order_by(desc(User.points)).limit(10)).all()
            list_str = "\n".join([f"{i+1}. {u.name} — *{u.points or 0}* pts" for i, u in enumerate(top_users)]) or "Belum ada data."
            text = f"*🏆 Top 10 Leaderboard Poin:*\n\n{list_str}"
        await query.edit_message_text(text, parse_mode="Markdown", reply_markup=back_kb)
