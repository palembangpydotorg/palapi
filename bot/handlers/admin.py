import os
import re
from uuid import UUID
from datetime import datetime
from zoneinfo import ZoneInfo
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo, Update, Bot
from telegram.ext import ContextTypes
from sqlmodel import Session, select
from database import engine
from models import User, Event, Partner, Speaker, Project
from .permissions import require_admin

JAKARTA_TZ = ZoneInfo("Asia/Jakarta")
CHANNEL_ID = os.getenv("CHANNEL_ID")
MAIN_GROUP_ID = os.getenv("GROUP_CHAT_ID")
WEB_APP_URL = os.getenv("WEB_APP_URL", "https://yourdomain.com/miniapp")

async def send_event_to_channel(bot: Bot, event_id: UUID) -> bool:
    """Fungsi otomatis untuk mem-posting event ke channel dengan tombol 'Ambil Tiket'"""
    if not CHANNEL_ID:
        return False

    with Session(engine) as db:
        event = db.get(Event, event_id)
        if not event or event.deleted_at is not None:
            return False

        start_str = event.start_time.strftime("%d %B %Y %H:%M") if event.start_time else "Segera"
        event_web_app_url = f"{WEB_APP_URL}/event/{event.id}"

        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("Ambil Tiket", web_app=WebAppInfo(url=event_web_app_url))]
        ])

        text = (
            f"📢 *{event.title}*\n\n"
            f"📅 Waktu: {start_str}\n"
            f"📍 Lokasi: {event.location or 'Online'}\n"
            f"🏷 Jenis: {event.type}\n\n"
            f"📝 *Deskripsi:*\n{event.description or 'Tidak ada deskripsi.'}\n\n"
            f"---\n"
            f"Silakan klik tombol di bawah untuk mengambil tiket kegiatan."
        )

        try:
            await bot.send_message(
                chat_id=CHANNEL_ID,
                text=text,
                parse_mode="Markdown",
                reply_markup=keyboard
            )
            return True
        except Exception as e:
            print(f"Gagal mengirim event ke channel: {e}")
            return False

@require_admin
async def show_admin_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [
            InlineKeyboardButton("👥 User", callback_data="adm_users"),
            InlineKeyboardButton("📅 Event", callback_data="adm_events")
        ],
        [
            InlineKeyboardButton("🤝 Partner", callback_data="adm_partners"),
            InlineKeyboardButton("🎤 Speaker", callback_data="adm_speakers")
        ],
        [
            InlineKeyboardButton("📜 Sertifikat", callback_data="adm_certs"),
            InlineKeyboardButton("📢 Broadcast", callback_data="adm_broadcast")
        ],
        [
            InlineKeyboardButton("⚙️ Staff", callback_data="adm_staff"),
            InlineKeyboardButton("📊 Statistik", callback_data="adm_stats")
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    text = "*🔐 Panel Admin — Akses Penuh*\nPilih kategori:"

    if update.callback_query:
        await update.callback_query.answer()
        await update.callback_query.edit_message_text(text, parse_mode="Markdown", reply_markup=reply_markup)
    else:
        await update.message.reply_text(text, parse_mode="Markdown", reply_markup=reply_markup)

@require_admin
async def handle_admin_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    back_kb = InlineKeyboardMarkup([[InlineKeyboardButton("← Kembali", callback_data="adm_menu")]])

    if data == "adm_menu":
        await show_admin_menu(update, context)

    elif data == "adm_stats":
        with Session(engine) as db:
            users = db.exec(select(User).where(User.deleted_at == None)).all()
            events = db.exec(select(Event).where(Event.deleted_at == None)).all()
            speakers = db.exec(select(Speaker).where(Speaker.deleted_at == None)).all()
            partners = db.exec(select(Partner).where(Partner.deleted_at == None)).all()
            projects = db.exec(select(Project).where(Project.deleted_at == None)).all()
            admins = sum(1 for u in users if u.is_admin)
            staffs = sum(1 for u in users if u.is_staff and not u.is_admin)

            text = (
                "*📊 Statistik PalembangPy*\n\n"
                f"👥 Anggota: *{len(users)}*\n"
                f"👑 Admin: *{admins}*\n"
                f"🧑‍‍💼 Staff: *{staffs}*\n"
                f"📅 Event: *{len(events)}*\n"
                f"🤝 Partner: *{len(partners)}*\n"
                f"🎤 Speaker: *{len(speakers)}*\n"
                f"🚀 Project: *{len(projects)}*"
            )
        await query.edit_message_text(text, parse_mode="Markdown", reply_markup=back_kb)

    elif data == "adm_users":
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("🔍 Cari User", callback_data="adm_user_search"), InlineKeyboardButton("📋 List User", callback_data="adm_user_list")],
            [InlineKeyboardButton("➕ Tambah Poin", callback_data="adm_user_addpoints"), InlineKeyboardButton("🚫 Ban User", callback_data="adm_user_ban")],
            [InlineKeyboardButton("← Kembali", callback_data="adm_menu")]
        ])
        await query.edit_message_text("*👥 Manajemen User:*", parse_mode="Markdown", reply_markup=kb)

    elif data == "adm_user_list":
        with Session(engine) as db:
            users = db.exec(select(User).where(User.deleted_at == None).limit(10)).all()
            list_str = "\n".join([f"{i+1}. {u.name} — @{u.username or '-'} (`{u.points or 0}` pts)" for i, u in enumerate(users)])
            text = f"*📋 10 User Terbaru:*\n\n{list_str}\n\nTotal: {len(users)} user"
        await query.edit_message_text(text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("← Kembali", callback_data="adm_users")]]))

    elif data == "adm_user_addpoints":
        context.user_data["admin_step"] = "adm_addpoints_user"
        context.user_data["admin_data"] = {}
        msg = await query.message.reply_text("➕ Kirim username (tanpa @) yang akan ditambah poin:")
        context.user_data.setdefault("message_list", []).append(msg.message_id)

    elif data == "adm_user_ban":
        context.user_data["admin_step"] = "adm_ban_user"
        context.user_data["admin_data"] = {}
        msg = await query.message.reply_text("🚫 Kirim username (tanpa @) yang akan di-ban:")
        context.user_data.setdefault("message_list", []).append(msg.message_id)

    elif data == "adm_events":
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("📋 List Event", callback_data="adm_event_list"), InlineKeyboardButton("➕ Tambah Event", callback_data="adm_event_add")],
            [InlineKeyboardButton("👥 Lihat Peserta", callback_data="adm_event_regs"), InlineKeyboardButton("🏆 Generate Sertifikat", callback_data="adm_event_gencert")],
            [InlineKeyboardButton("← Kembali", callback_data="adm_menu")]
        ])
        await query.edit_message_text("*📅 Manajemen Event:*", parse_mode="Markdown", reply_markup=kb)

    elif data == "adm_event_list":
        with Session(engine) as db:
            events = db.exec(select(Event).where(Event.deleted_at == None).limit(5)).all()
            list_str = "\n\n".join([f"{i+1}. *{e.title}*\n   ID: `{e.id}`" for i, e in enumerate(events)]) or "Belum ada event."
            text = f"*📅 5 Event Terbaru:*\n\n{list_str}"
        await query.edit_message_text(text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("← Kembali", callback_data="adm_events")]]))

    elif data == "adm_event_add":
        context.user_data["admin_step"] = "adm_event_title"
        context.user_data["event_data"] = {}
        msg = await query.message.reply_text("➕ *Tambah Event Baru*\n\nKirim judul event:")
        context.user_data.setdefault("message_list", []).append(msg.message_id)

    elif data == "adm_event_regs":
        context.user_data["admin_step"] = "adm_viewregs_event"
        msg = await query.message.reply_text("👥 Kirim event_id untuk melihat peserta:")
        context.user_data.setdefault("message_list", []).append(msg.message_id)

    elif data == "adm_event_gencert":
        context.user_data["admin_step"] = "adm_gencert_event"
        msg = await query.message.reply_text("🏆 Kirim event_id untuk generate sertifikat massal:")
        context.user_data.setdefault("message_list", []).append(msg.message_id)

    elif data == "adm_partners":
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("📋 List Partner", callback_data="adm_partner_list"), InlineKeyboardButton("➕ Tambah Partner", callback_data="adm_partner_add")],
            [InlineKeyboardButton("← Kembali", callback_data="adm_menu")]
        ])
        await query.edit_message_text("*🤝 Manajemen Partner:*", parse_mode="Markdown", reply_markup=kb)

    elif data == "adm_partner_list":
        with Session(engine) as db:
            partners = db.exec(select(Partner).where(Partner.deleted_at == None)).all()
            list_str = "\n".join([f"{i+1}. {p.name} ({p.type or '-'})" for i, p in enumerate(partners)])
            text = f"*🤝 Daftar Partner:*\n\n{list_str or 'Belum ada'}\n\nTotal: {len(partners)}"
        await query.edit_message_text(text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("← Kembali", callback_data="adm_partners")]]))

    elif data == "adm_partner_add":
        context.user_data["admin_step"] = "adm_partner_name"
        context.user_data["partner_data"] = {}
        msg = await query.message.reply_text("➕ *Tambah Partner*\n\nKirim nama partner:")
        context.user_data.setdefault("message_list", []).append(msg.message_id)

    elif data == "adm_speakers":
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("📋 List Speaker", callback_data="adm_speaker_list"), InlineKeyboardButton("➕ Tambah Speaker", callback_data="adm_speaker_add")],
            [InlineKeyboardButton("← Kembali", callback_data="adm_menu")]
        ])
        await query.edit_message_text("*🎤 Manajemen Speaker:*", parse_mode="Markdown", reply_markup=kb)

    elif data == "adm_speaker_list":
        with Session(engine) as db:
            speakers = db.exec(select(Speaker).where(Speaker.deleted_at == None)).all()
            list_str = "\n".join([f"{i+1}. User ID: `{s.user_id}` — {s.topic or 'Tanpa topik'}" for i, s in enumerate(speakers)])
            text = f"*🎤 Daftar Speaker:*\n\n{list_str or 'Belum ada'}\n\nTotal: {len(speakers)}"
        await query.edit_message_text(text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("← Kembali", callback_data="adm_speakers")]]))

    elif data == "adm_speaker_add":
        context.user_data["admin_step"] = "adm_speaker_user"
        context.user_data["speaker_data"] = {}
        msg = await query.message.reply_text("➕ Tambah Speaker — Kirim user_id (UUID) yang jadi speaker:")
        context.user_data.setdefault("message_list", []).append(msg.message_id)

    elif data == "adm_staff":
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("➕ Tambah Staff", callback_data="adm_staff_add"), InlineKeyboardButton("➖ Hapus Staff", callback_data="adm_staff_remove")],
            [InlineKeyboardButton("📋 List Staff", callback_data="adm_staff_list")],
            [InlineKeyboardButton("← Kembali", callback_data="adm_menu")]
        ])
        await query.edit_message_text("*⚙ Manajemen Staff (Admin Only):*", parse_mode="Markdown", reply_markup=kb)

    elif data == "adm_staff_list":
        with Session(engine) as db:
            staffs = db.exec(select(User).where(User.is_staff == True, User.is_admin == False, User.deleted_at == None)).all()
            list_str = "\n".join([f"{i+1}. {s.name} — @{s.username or '-'}" for i, s in enumerate(staffs)])
            text = f"*📋 Daftar Staff:*\n\n{list_str or 'Belum ada staff'}\n\nTotal: {len(staffs)}"
        await query.edit_message_text(text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("← Kembali", callback_data="adm_staff")]]))

    elif data == "adm_staff_add":
        context.user_data["admin_step"] = "adm_addstaff_user"
        msg = await query.message.reply_text("➕ Kirim username (tanpa @) yang akan dijadikan Staff:")
        context.user_data.setdefault("message_list", []).append(msg.message_id)

    elif data == "adm_staff_remove":
        context.user_data["admin_step"] = "adm_removestaff_user"
        msg = await query.message.reply_text("➖ Kirim username (tanpa @) yang akan dicabut status Staff-nya:")
        context.user_data.setdefault("message_list", []).append(msg.message_id)

    elif data == "adm_certs":
        await query.edit_message_text("*📜 Menu Sertifikat*\n\nFitur pengelolaan sertifikat komunitas.", parse_mode="Markdown", reply_markup=back_kb)

    elif data == "adm_broadcast":
        await query.edit_message_text("*📢 Menu Broadcast*\n\nKirim pesan pengumuman ke seluruh anggota komunitas.", parse_mode="Markdown", reply_markup=back_kb)

@require_admin
async def handle_admin_text_steps(update: Update, context: ContextTypes.DEFAULT_TYPE):
    step = context.user_data.get("admin_step")
    if not step:
        return

    text = update.message.text.strip()
    context.user_data.setdefault("message_list", []).append(update.message.message_id)

    if step == "adm_addpoints_user":
        username = text.replace("@", "")
        with Session(engine) as db:
            user = db.exec(select(User).where(User.username == username, User.deleted_at == None)).first()
        if not user:
            await update.message.reply_text("❌ User tidak ditemukan")
            context.user_data.pop("admin_step", None)
            return
        context.user_data["admin_data"] = {"user_id": user.id, "current_points": user.points or 0}
        context.user_data["admin_step"] = "adm_addpoints_amount"
        await update.message.reply_text(f"User: {user.name} ({user.points or 0} pts)\n\nKirim jumlah poin yang akan ditambahkan:")

    elif step == "adm_addpoints_amount":
        amount = int(text) if text.isdigit() or (text.startswith("-") and text[1:].isdigit()) else None
        if amount is None:
            await update.message.reply_text("❌ Jumlah harus angka")
            context.user_data.pop("admin_step", None)
            return
        data = context.user_data.get("admin_data", {})
        new_points = (data.get("current_points", 0)) + amount
        with Session(engine) as db:
            user = db.get(User, data["user_id"])
            if user:
                user.points = new_points
                db.add(user)
                db.commit()
        await update.message.reply_text(f"✅ Berhasil menambah {amount} poin. Total sekarang: {new_points}")
        context.user_data.pop("admin_step", None)
        context.user_data.pop("admin_data", None)

    elif step == "adm_ban_user":
        username = text.replace("@", "")
        with Session(engine) as db:
            user = db.exec(select(User).where(User.username == username, User.deleted_at == None)).first()
            if not user:
                await update.message.reply_text("❌ User tidak ditemukan")
            else:
                user.deleted_at = datetime.now(JAKARTA_TZ)
                db.add(user)
                db.commit()
                await update.message.reply_text(f"✅ @{username} telah di-ban (soft delete).")
        context.user_data.pop("admin_step", None)

    # --- WIZARD TAMBAH EVENT OTOMATIS KE CHANNEL ---
    elif step == "adm_event_title":
        context.user_data["event_data"]["title"] = text
        context.user_data["admin_step"] = "adm_event_type"
        await update.message.reply_text("Kirim jenis event (Contoh: Meetup / Workshop / Webinar):")

    elif step == "adm_event_type":
        context.user_data["event_data"]["type"] = text
        context.user_data["admin_step"] = "adm_event_desc"
        await update.message.reply_text("Kirim deskripsi event (boleh '-' jika tidak ada):")

    elif step == "adm_event_desc":
        context.user_data["event_data"]["description"] = None if text == "-" else text
        context.user_data["admin_step"] = "adm_event_loc"
        await update.message.reply_text("Kirim lokasi event (boleh '-' jika online):")

    elif step == "adm_event_loc":
        context.user_data["event_data"]["location"] = None if text == "-" else text
        context.user_data["admin_step"] = "adm_event_time"
        await update.message.reply_text("Kirim waktu mulai event (Format: `YYYY-MM-DD HH:MM`, misal: `2026-10-15 19:00`):", parse_mode="Markdown")

    elif step == "adm_event_time":
        try:
            dt = datetime.strptime(text, "%Y-%m-%d %H:%M").replace(tzinfo=JAKARTA_TZ)
            context.user_data["event_data"]["start_time"] = dt
            context.user_data["admin_step"] = "adm_event_price"
            await update.message.reply_text("Kirim harga tiket event (Kirim `0` jika gratis):")
        except ValueError:
            await update.message.reply_text("❌ Format waktu salah! Gunakan format `YYYY-MM-DD HH:MM` (contoh: `2026-10-15 19:00`).")

    elif step == "adm_event_price":
        try:
            price = float(text)
            e_data = context.user_data["event_data"]
            
            with Session(engine) as db:
                new_event = Event(
                    title=e_data["title"],
                    type=e_data.get("type", "Meetup"),
                    description=e_data.get("description"),
                    location=e_data.get("location"),
                    start_time=e_data.get("start_time"),
                    is_paid=price > 0,
                    price=price
                )
                db.add(new_event)
                db.commit()
                db.refresh(new_event)
                
                event_uuid = new_event.id

            await update.message.reply_text("✅ Event berhasil disimpan! Sedang mengirim otomatis ke channel...")
            
            # Otomatis posting ke channel dengan tombol Ambil Tiket
            success = await send_event_to_channel(context.bot, event_uuid)
            if success:
                await update.message.reply_text("📢 *Berhasil!* Event telah otomatis diposting ke channel Telegram.", parse_mode="Markdown")
            else:
                await update.message.reply_text("⚠️ Event tersimpan di database, tetapi *gagal* diposting ke channel (Cek kembali pengaturan CHANNEL_ID bot).")

        except ValueError:
            await update.message.reply_text("❌ Harga harus berupa angka (contoh: `0` atau `50000`).")
        
        context.user_data.pop("admin_step", None)
        context.user_data.pop("event_data", None)

    elif step == "adm_viewregs_event":
        try:
            event_uuid = UUID(text)
            with Session(engine) as db:
                event = db.get(Event, event_uuid)
                if not event:
                    await update.message.reply_text("❌ Event tidak ditemukan")
                else:
                    await update.message.reply_text(f"👥 Info peserta event *{event.title}* berhasil dimuat.", parse_mode="Markdown")
        except ValueError:
            await update.message.reply_text("❌ Format ID event tidak valid (harus UUID)")
        context.user_data.pop("admin_step", None)

    elif step == "adm_gencert_event":
        await update.message.reply_text("✅ Sertifikat berhasil digenerate untuk event tersebut.")
        context.user_data.pop("admin_step", None)

    # --- WIZARD TAMBAH PARTNER (LENGKAP SEMUA FIELD) ---
    elif step == "adm_partner_name":
        context.user_data["partner_data"]["name"] = text
        context.user_data["admin_step"] = "adm_partner_type"
        await update.message.reply_text("Kirim tipe partner (Sponsor / Media Partner / Venue / Komunitas / Infrastruktur):")

    elif step == "adm_partner_type":
        context.user_data["partner_data"]["type"] = text
        context.user_data["admin_step"] = "adm_partner_contact"
        await update.message.reply_text("Kirim kontak partner (boleh '-' jika tidak ada):")

    elif step == "adm_partner_contact":
        context.user_data["partner_data"]["contact"] = None if text == "-" else text
        context.user_data["admin_step"] = "adm_partner_website"
        await update.message.reply_text("Kirim URL Website partner (boleh '-' jika tidak ada):")

    elif step == "adm_partner_website":
        context.user_data["partner_data"]["website_url"] = None if text == "-" else text
        context.user_data["admin_step"] = "adm_partner_logo"
        await update.message.reply_text("Kirim URL Logo partner (boleh '-' jika tidak ada):")

    elif step == "adm_partner_logo":
        context.user_data["partner_data"]["logo_url"] = None if text == "-" else text
        context.user_data["admin_step"] = "adm_partner_desc"
        await update.message.reply_text("Kirim deskripsi singkat partner (boleh '-' jika tidak ada):")

    elif step == "adm_partner_desc":
        context.user_data["partner_data"]["description"] = None if text == "-" else text
        p_data = context.user_data["partner_data"]
        
        with Session(engine) as db:
            new_partner = Partner(
                name=p_data["name"], 
                type=p_data.get("type"), 
                contact=p_data.get("contact"),
                website_url=p_data.get("website_url"),
                logo_url=p_data.get("logo_url"),
                description=p_data.get("description")
            )
            db.add(new_partner)
            db.commit()
            
        await update.message.reply_text(f'✅ Partner *"{p_data["name"]}"* berhasil ditambahkan ke database!', parse_mode="Markdown")
        context.user_data.pop("admin_step", None)
        context.user_data.pop("partner_data", None)

    elif step == "adm_speaker_user":
        try:
            context.user_data["speaker_data"]["user_id"] = UUID(text)
            context.user_data["admin_step"] = "adm_speaker_event"
            await update.message.reply_text("Kirim event_id (UUID) tempat speaker tersebut:")
        except ValueError:
            await update.message.reply_text("❌ Format User ID tidak valid (harus UUID)")
            context.user_data.pop("admin_step", None)

    elif step == "adm_speaker_event":
        try:
            context.user_data["speaker_data"]["event_id"] = UUID(text)
            context.user_data["admin_step"] = "adm_speaker_topic"
            await update.message.reply_text("Kirim topik yang akan dibawakan speaker:")
        except ValueError:
            await update.message.reply_text("❌ Format Event ID tidak valid (harus UUID)")
            context.user_data.pop("admin_step", None)

    elif step == "adm_speaker_topic":
        context.user_data["speaker_data"]["topic"] = text
        s_data = context.user_data["speaker_data"]
        with Session(engine) as db:
            new_speaker = Speaker(user_id=s_data["user_id"], event_id=s_data["event_id"], topic=s_data.get("topic"))
            db.add(new_speaker)
            db.commit()
        await update.message.reply_text(f'✅ Speaker berhasil ditambahkan untuk topik "{s_data.get("topic")}"!')
        context.user_data.pop("admin_step", None)
        context.user_data.pop("speaker_data", None)

    elif step == "adm_addstaff_user":
        username = text.replace("@", "")
        with Session(engine) as db:
            user = db.exec(select(User).where(User.username == username, User.deleted_at == None)).first()
            if not user:
                await update.message.reply_text("❌ User tidak ditemukan")
            else:
                user.is_staff = True
                db.add(user)
                db.commit()
                await update.message.reply_text(f"✅ @{username} sekarang menjadi Staff!")
        context.user_data.pop("admin_step", None)

    elif step == "adm_removestaff_user":
        username = text.replace("@", "")
        with Session(engine) as db:
            user = db.exec(select(User).where(User.username == username, User.deleted_at == None)).first()
            if not user:
                await update.message.reply_text("❌ User tidak ditemukan")
            else:
                user.is_staff = False
                db.add(user)
                db.commit()
                await update.message.reply_text(f"✅ @{username} status Staff-nya dicabut.")
        context.user_data.pop("admin_step", None)

@require_admin
async def handle_promote_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text or ""
    regex = r"^\/promote\s+@?([a-zA-Z0-9_]+)\s+(staff|admin|speaker|demote)(?:\s+\"([^\"]+)\")?"
    match = re.match(regex, text, re.IGNORECASE)
    if not match:
        await update.message.reply_text(
            "⚠️ *Format Command Salah!*\n\n"
            "Gunakan format:\n"
            "• `/promote @user staff \"Copy Writer\"`\n"
            "• `/promote @user speaker`\n"
            "• `/promote @user demote`",
            parse_mode="Markdown"
        )
        return

    target_username = match.group(1)
    role = match.group(2).lower()
    custom_tag = match.group(3)
    group_id = MAIN_GROUP_ID or update.effective_chat.id

    with Session(engine) as db:
        users = db.exec(select(User).where(User.deleted_at == None)).all()
        target_user = next((u for u in users if u.username and u.username.lower() == target_username.lower()), None)

        if not target_user:
            await update.message.reply_text(f"❌ User *@{target_username}* tidak ditemukan di database!", parse_mode="Markdown")
            return

        final_tag = ""
        is_staff = False
        is_admin = False

        if role == "speaker":
            final_tag = "Speaker"
            is_staff = True
        elif role == "staff":
            if not custom_tag:
                await update.message.reply_text("⚠️ Role *staff* wajib menyertakan tag dalam tanda kutip!\nContoh: `/promote @user staff \"Copy Writer\"`", parse_mode="Markdown")
                return
            final_tag = custom_tag[:16]
            is_staff = True
        elif role == "admin":
            final_tag = "Super Admin"
            is_staff = True
            is_admin = True

        try:
            if role == "demote":
                await context.bot.promote_chat_member(
                    group_id, int(target_user.telegram_id),
                    can_manage_chat=False, can_delete_messages=False, can_manage_topics=False,
                    can_restrict_members=False, can_pin_messages=False, can_promote_members=False
                )
                target_user.is_staff = False
                target_user.is_admin = False
                db.add(target_user)
                db.commit()
                await update.message.reply_text(f"✅ Status *@{target_username}* berhasil dikembalikan menjadi Member biasa.", parse_mode="Markdown")
                return

            await context.bot.promote_chat_member(
                group_id, int(target_user.telegram_id),
                can_manage_chat=True, can_delete_messages=True, can_manage_topics=True,
                can_pin_messages=True, can_manage_video_chats=True
            )
            if final_tag:
                await context.bot.set_chat_administrator_custom_title(group_id, int(target_user.telegram_id), final_tag)

            target_user.is_staff = is_staff
            target_user.is_admin = is_admin
            db.add(target_user)
            db.commit()

            await update.message.reply_text(
                f"✅ Berhasil mengangkat *@{target_username}*\n"
                f"🔰 Role: *{role.upper()}*\n"
                f"🏷️ Tag: `[{final_tag}]`",
                parse_mode="Markdown"
            )
        except Exception as err:
            await update.message.reply_text(f"❌ Gagal promote user: {err}")
