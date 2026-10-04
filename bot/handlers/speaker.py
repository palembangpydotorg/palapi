import os
from uuid import UUID
from datetime import datetime
from zoneinfo import ZoneInfo
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes
from sqlmodel import Session, select
from database import engine
from models import User, Event, Speaker, SpeakerMaterial

JAKARTA_TZ = ZoneInfo("Asia/Jakarta")

ALLOWED_EXTENSIONS = {".pdf", ".pptx", ".docx", ".zip", ".xlsx"}
ALLOWED_MIME_TYPES = {
    "application/pdf",
    "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/zip",
    "application/x-zip-compressed",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
}
MAX_FILE_SIZE = 5 * 1024 * 1024

async def show_speaker_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [
            InlineKeyboardButton("🎤 Daftar Speaker & Topik", callback_data="speaker_list"),
            InlineKeyboardButton("📤 Upload Materi/Slide", callback_data="speaker_upload_start")
        ],
        [
            InlineKeyboardButton("← Kembali ke Menu", callback_data="member_menu")
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    text = "*🎤 Menu Pembicara (Speaker)*\n\nPilih opsi di bawah ini:"

    if update.callback_query:
        await update.callback_query.answer()
        await update.callback_query.edit_message_text(text, parse_mode="Markdown", reply_markup=reply_markup)
    else:
        await update.message.reply_text(text, parse_mode="Markdown", reply_markup=reply_markup)

async def handle_speaker_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    back_kb = InlineKeyboardMarkup([[InlineKeyboardButton("← Kembali", callback_data="speaker_menu")]])

    if data == "speaker_menu":
        await show_speaker_menu(update, context)

    elif data == "speaker_list":
        with Session(engine) as db:
            speakers = db.exec(select(Speaker).where(Speaker.deleted_at == None)).all()
            list_items = []
            for i, s in enumerate(speakers):
                user = db.get(User, s.user_id)
                event = db.get(Event, s.event_id)
                name = user.name if user else "Unknown"
                event_title = event.title if event else "Unknown Event"
                topic = s.topic or "Tanpa Topik"
                list_items.append(f"{i+1}. *{name}*\n   Topik: {topic}\n   Event: _{event_title}_")
            
            text = f"*🎤 Daftar Pembicara Komunitas:*\n\n" + ("\n\n".join(list_items) or "Belum ada speaker terdaftar.")
        await query.edit_message_text(text, parse_mode="Markdown", reply_markup=back_kb)

    elif data == "speaker_upload_start":
        tg_id = str(query.from_user.id)
        with Session(engine) as db:
            user = db.exec(select(User).where(User.telegram_id == tg_id, User.deleted_at == None)).first()
            if not user:
                await query.edit_message_text("❌ Akun Anda belum terdaftar.", reply_markup=back_kb)
                return
            
            speaker = db.exec(select(Speaker).where(Speaker.user_id == user.id, Speaker.deleted_at == None)).first()
            if not speaker:
                await query.edit_message_text("❌ Anda belum terdaftar sebagai pembicara pada event manapun.", reply_markup=back_kb)
                return

        context.user_data["speaker_step"] = "speaker_material_title"
        context.user_data["material_data"] = {}
        msg = await query.message.reply_text("📤 *Upload Materi Presentasi*\n\nKirim judul materi/slide Anda:")
        context.user_data.setdefault("message_list", []).append(msg.message_id)

async def handle_speaker_text_steps(update: Update, context: ContextTypes.DEFAULT_TYPE):
    step = context.user_data.get("speaker_step")
    if not step:
        return

    text = update.message.text.strip()
    context.user_data.setdefault("message_list", []).append(update.message.message_id)

    if step == "speaker_material_title":
        context.user_data["material_data"]["title"] = text
        context.user_data["speaker_step"] = "speaker_material_desc"
        msg = await update.message.reply_text("Kirim deskripsi singkat materi (boleh '-' jika tidak ada):")
        context.user_data["message_list"].append(msg.message_id)

    elif step == "speaker_material_desc":
        context.user_data["material_data"]["description"] = None if text == "-" else text
        context.user_data["speaker_step"] = "speaker_material_file"
        msg = await update.message.reply_text("Silakan kirim file dokumen/PDF/slide materi Anda (Format: PDF, PPTX, DOCX, ZIP):")
        context.user_data["message_list"].append(msg.message_id)

async def handle_speaker_document(update: Update, context: ContextTypes.DEFAULT_TYPE):
    step = context.user_data.get("speaker_step")
    if step != "speaker_material_file":
        return

    doc = update.message.document
    if not doc:
        await update.message.reply_text("❌ Harap kirimkan file dokumen yang valid.")
        return

    file_name = doc.file_name or "document"
    ext = os.path.splitext(file_name)[1].lower()
    mime_type = doc.mime_type or ""
    file_size = doc.file_size or 0

    if ext not in ALLOWED_EXTENSIONS or mime_type not in ALLOWED_MIME_TYPES:
        await update.message.reply_text("❌ *Ditolak!* Jenis file atau ekstensi tidak diizinkan demi keamanan sistem.", parse_mode="Markdown")
        context.user_data.pop("speaker_step", None)
        context.user_data.pop("material_data", None)
        return

    if file_size > MAX_FILE_SIZE:
        await update.message.reply_text("❌ *Ditolak!* Ukuran file melebihi batas maksimal 5 MB.", parse_mode="Markdown")
        context.user_data.pop("speaker_step", None)
        context.user_data.pop("material_data", None)
        return

    sanitized_filename = os.path.basename(file_name)
    context.user_data.setdefault("message_list", []).append(update.message.message_id)
    mat_data = context.user_data["material_data"]
    tg_id = str(update.effective_user.id)

    with Session(engine) as db:
        user = db.exec(select(User).where(User.telegram_id == tg_id, User.deleted_at == None)).first()
        if user:
            speaker = db.exec(select(Speaker).where(Speaker.user_id == user.id, Speaker.deleted_at == None)).first()
            if speaker:
                new_material = SpeakerMaterial(
                    speaker_id=speaker.id,
                    title=mat_data["title"],
                    description=mat_data.get("description"),
                    file_path=doc.file_id,
                    file_original_name=sanitized_filename,
                    file_mime_type=mime_type,
                    file_size=file_size
                )
                db.add(new_material)
                db.commit()
                await update.message.reply_text(f"✅ Materi *{mat_data['title']}* berhasil diunggah dan terverifikasi aman!", parse_mode="Markdown")

    context.user_data.pop("speaker_step", None)
    context.user_data.pop("material_data", None)
