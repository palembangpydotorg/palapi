from uuid import UUID
from datetime import datetime
from zoneinfo import ZoneInfo
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes
from sqlmodel import Session, select
from database import engine
from models import User, Event, Speaker, Project
from .permissions import require_staff

JAKARTA_TZ = ZoneInfo("Asia/Jakarta")

@require_staff
async def show_staff_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [
            InlineKeyboardButton("👥 User", callback_data="staff_users"),
            InlineKeyboardButton("📅 Event", callback_data="staff_events")
        ],
        [
            InlineKeyboardButton("🎤 Speaker", callback_data="staff_speakers"),
            InlineKeyboardButton("📁 Project", callback_data="staff_projects")
        ],
        [
            InlineKeyboardButton("📊 Statistik", callback_data="staff_stats")
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    text = "*⚙️ Panel Staff — Area Kerja*\nPilih menu:"

    if update.callback_query:
        await update.callback_query.answer()
        await update.callback_query.edit_message_text(text, parse_mode="Markdown", reply_markup=reply_markup)
    else:
        await update.message.reply_text(text, parse_mode="Markdown", reply_markup=reply_markup)

@require_staff
async def handle_staff_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    back_kb = InlineKeyboardMarkup([[InlineKeyboardButton("← Kembali", callback_data="staff_menu")]])

    if data == "staff_menu":
        await show_staff_menu(update, context)

    elif data == "staff_stats":
        with Session(engine) as db:
            users = db.exec(select(User).where(User.deleted_at == None)).all()
            events = db.exec(select(Event).where(Event.deleted_at == None)).all()
            speakers = db.exec(select(Speaker).where(Speaker.deleted_at == None)).all()
            projects = db.exec(select(Project).where(Project.deleted_at == None)).all()
            admins = sum(1 for u in users if u.is_admin)
            staffs = sum(1 for u in users if u.is_staff and not u.is_admin)

            text = (
                "*📊 Statistik Komunitas*\n\n"
                f"👥 Anggota: *{len(users)}*\n"
                f"👑 Admin: *{admins}*\n"
                f"🧑‍💼 Staff: *{staffs}*\n"
                f"📅 Event: *{len(events)}*\n"
                f"🎤 Speaker: *{len(speakers)}*\n"
                f"🚀 Project: *{len(projects)}*"
            )
        await query.edit_message_text(text, parse_mode="Markdown", reply_markup=back_kb)

    elif data == "staff_users":
        with Session(engine) as db:
            users = db.exec(select(User).where(User.deleted_at == None).limit(10)).all()
            list_str = "\n".join([f"{i+1}. {u.name} — @{u.username or '-'} (`{u.points or 0}` pts)" for i, u in enumerate(users)])
            text = f"*👥 Daftar Anggota (10 Teratas):*\n\n{list_str}\n\nTotal: {len(users)} ditampilkan"
        await query.edit_message_text(text, parse_mode="Markdown", reply_markup=back_kb)

    elif data == "staff_events":
        with Session(engine) as db:
            events = db.exec(select(Event).where(Event.deleted_at == None).limit(5)).all()
            list_str = "\n\n".join([f"{i+1}. *{e.title}*\n   ID: `{e.id}`" for i, e in enumerate(events)]) or "Belum ada event."
            text = f"*📅 Daftar Event Terbaru:*\n\n{list_str}"
        await query.edit_message_text(text, parse_mode="Markdown", reply_markup=back_kb)

    elif data == "staff_speakers":
        with Session(engine) as db:
            speakers = db.exec(select(Speaker).where(Speaker.deleted_at == None)).all()
            list_str = "\n".join([f"{i+1}. User ID: `{s.user_id}` — {s.topic or 'Tanpa topik'}" for i, s in enumerate(speakers)])
            text = f"*🎤 Daftar Speaker:*\n\n{list_str or 'Belum ada'}\n\nTotal: {len(speakers)}"
        await query.edit_message_text(text, parse_mode="Markdown", reply_markup=back_kb)

    elif data == "staff_projects":
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("📋 List Project", callback_data="staff_project_list"), InlineKeyboardButton("➕ Tambah Project", callback_data="staff_project_add")],
            [InlineKeyboardButton("← Kembali", callback_data="staff_menu")]
        ])
        await query.edit_message_text("*📁 Manajemen Project:*", parse_mode="Markdown", reply_markup=kb)

    elif data == "staff_project_list":
        with Session(engine) as db:
            projects = db.exec(select(Project).where(Project.deleted_at == None)).all()
            list_str = "\n".join([f"{i+1}. *{p.title}* ({p.status})" for i, p in enumerate(projects)])
            text = f"*📁 Daftar Project:*\n\n{list_str or 'Belum ada project.'}\n\nTotal: {len(projects)}"
        await query.edit_message_text(text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("← Kembali", callback_data="staff_projects")]]))

    elif data == "staff_project_add":
        context.user_data["staff_step"] = "staff_project_title"
        context.user_data["project_data"] = {}
        msg = await query.message.reply_text("➕ Tambah Project — Kirim judul project:")
        context.user_data.setdefault("message_list", []).append(msg.message_id)

@require_staff
async def handle_staff_text_steps(update: Update, context: ContextTypes.DEFAULT_TYPE):
    step = context.user_data.get("staff_step")
    if not step:
        return

    text = update.message.text.strip()
    context.user_data.setdefault("message_list", []).append(update.message.message_id)

    if step == "staff_project_title":
        context.user_data["project_data"]["title"] = text
        context.user_data["staff_step"] = "staff_project_desc"
        await update.message.reply_text("Kirim deskripsi project (boleh '-' jika tidak ada):")

    elif step == "staff_project_desc":
        context.user_data["project_data"]["description"] = None if text == "-" else text
        context.user_data["staff_step"] = "staff_project_github"
        await update.message.reply_text("Kirim URL repository GitHub (boleh '-' jika tidak ada):")

    elif step == "staff_project_github":
        context.user_data["project_data"]["github_url"] = None if text == "-" else text
        context.user_data["staff_step"] = "staff_project_tags"
        await update.message.reply_text("Kirim tags project (contoh: python,fastapi,docker):")

    elif step == "staff_project_tags":
        context.user_data["project_data"]["tags"] = None if text == "-" else text
        p_data = context.user_data["project_data"]
        
        tg_id = str(update.effective_user.id)
        with Session(engine) as db:
            user = db.exec(select(User).where(User.telegram_id == tg_id, User.deleted_at == None)).first()
            if not user:
                await update.message.reply_text("❌ Akun Anda belum terdaftar di database.")
            else:
                new_project = Project(
                    title=p_data["title"],
                    description=p_data.get("description"),
                    github_url=p_data.get("github_url"),
                    tags=p_data.get("tags"),
                    user_id=user.id,
                    status="published"
                )
                db.add(new_project)
                db.commit()
                await update.message.reply_text(f'✅ Project "{p_data["title"]}" berhasil ditambahkan!')
        
        context.user_data.pop("staff_step", None)
        context.user_data.pop("project_data", None)
