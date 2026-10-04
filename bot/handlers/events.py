import os
from uuid import UUID
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo, Bot
from sqlmodel import Session, select
from database import engine
from models import Event

WEB_APP_URL = os.getenv("WEB_APP_URL", "https://yourdomain.com/miniapp")
CHANNEL_ID = os.getenv("CHANNEL_ID")

async def send_event_to_channel(bot: Bot, event_id: UUID) -> bool:
    """
    Mengambil data event dari database berdasarkan ID, 
    lalu mengirimkannya ke channel komunitas dengan satu tombol Mini App.
    """
    if not CHANNEL_ID:
        return False

    with Session(engine) as db:
        event = db.get(Event, event_id)
        if not event or event.deleted_at is not None:
            return False

        # Format waktu mulai event
        start_str = event.start_time.strftime("%d %B %Y %H:%M") if event.start_time else "Segera"
        
        # URL khusus Mini App untuk event tersebut
        event_web_app_url = f"{WEB_APP_URL}/event/{event.id}"

        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("Ambil Tiket", web_app=WebAppInfo(url=event_web_app_url))]
        ])

        text = (
            f"📢 *{event.title}*\n\n"
            f"📅 Waktu: {start_str}\n"
            f"📍 Lokasi: {event.location or 'Online'}\n"
            f"🏷️ Jenis: {event.type}\n\n"
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
