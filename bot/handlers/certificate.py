import os
from datetime import datetime
from zoneinfo import ZoneInfo
from telegram import Update, InputFile
from telegram.ext import ContextTypes
from sqlmodel import Session, select
from database import engine
from models import User, Event
from .permissions import require_admin

JAKARTA_TZ = ZoneInfo("Asia/Jakarta")

def generate_certificate_html(name: str, peserta_or_narasumber: str, event_title: str, date_str: str, cert_id: str, nim: str) -> str:
    return f"""<!DOCTYPE html>
<html lang="id">
<head>
    <meta charset="UTF-8">
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Cinzel:wght@600;700&family=Plus+Jakarta+Sans:wght@400;500;600;700&display=swap');
        
        body {{
            margin: 0;
            padding: 0;
            width: 1122px;
            height: 794px;
            background: #ffffff;
            font-family: 'Plus Jakarta Sans', sans-serif;
            color: #1e293b;
            display: flex;
            justify-content: center;
            align-items: center;
            box-sizing: border-box;
        }}
        
        .cert-container {{
            position: relative;
            width: 1042px;
            height: 714px;
            background: #ffffff;
            border: 3px solid #dc2626;
            box-shadow: 0 10px 30px rgba(0, 0, 0, 0.05);
            display: flex;
            flex-direction: column;
            justify-content: space-between;
            padding: 50px 70px;
            text-align: center;
            overflow: hidden;
            box-sizing: border-box;
        }}

        .bg-image {{
            position: absolute;
            bottom: -28rem;
            left: -10rem;
            width: 100%;
            opacity: 0.12;
            z-index: 0;
            pointer-events: none;
        }}
        
        .content {{
            position: relative;
            z-index: 1;
            display: flex;
            flex-direction: column;
            align-items: center;
            margin-top: 10px;
        }}
        
        .badge {{
            font-size: 13px;
            font-weight: 600;
            color: #ffffff;
            background: #dc2626;
            border: 1px solid #b91c1c;
            padding: 6px 20px;
            border-radius: 20px;
            letter-spacing: 3px;
            text-transform: uppercase;
            margin-bottom: 20px;
            box-shadow: 0 4px 12px rgba(220, 38, 38, 0.2);
        }}
        
        .title {{
            font-family: 'Cinzel', serif;
            font-size: 42px;
            font-weight: 700;
            color: #0f172a;
            letter-spacing: 3px;
            margin-bottom: 6px;
            text-transform: uppercase;
        }}
        
        .subtitle {{
            font-size: 14px;
            color: #64748b;
            text-transform: uppercase;
            letter-spacing: 2px;
            margin-bottom: 30px;
            }}
        
        .recipient {{
            font-family: 'Cinzel', serif;
            font-size: 40px;
            font-weight: 700;
            color: #dc2626;
            border-bottom: 2px solid rgba(220, 38, 38, 0.4);
            padding-bottom: 6px;
            margin-bottom: 22px;
            min-width: 600px;
            display: inline-block;
        }}
        
        .desc {{
            font-size: 16px;
            color: #334155;
            line-height: 1.6;
            max-width: 820px;
        }}
        
        .event-name {{
            color: #0f172a;
            font-weight: 700;
        }}
        
        .footer {{
            display: flex;
            justify-content: space-between;
            width: 100%;
            align-items: flex-end;
            position: relative;
            z-index: 1;
        }}
        
        .left-footer {{
            display: flex;
            align-items: center;
            gap: 15px;
            text-align: left;
        }}

        .qr-box {{
            width: 75px;
            height: 75px;
            background: #ffffff;
            border: 1px solid #cbd5e1;
            padding: 5px;
            border-radius: 6px;
            display: flex;
            justify-content: center;
            align-items: center;
        }}

        .cert-info {{
            display: flex;
            flex-direction: column;
            gap: 4px;
        }}

        .cert-id {{
            font-size: 11px;
            color: #64748b;
            font-family: monospace;
            letter-spacing: 1px;
        }}

        .verify-text {{
            font-size: 10px;
            color: #dc2626;
            font-weight: 700;
            text-transform: uppercase;
            letter-spacing: 1px;
        }}
        
        .signature-box {{
            text-align: center;
            border-top: 1px solid #cbd5e1;
            width: 200px;
            padding-top: 8px;
            font-size: 13px;
            color: #475569;
        }}
    </style>
</head>
<body>
    <div class="cert-container">
        <img class="bg-image" src="ampera.png" alt="Jembatan Ampera">
        
        <div class="content">
            <div class="badge">PalembangPy Community</div>
            <div class="title">Sertifikat Keikutsertaan</div>
            <div class="subtitle">Diberikan Dengan Bangga Kepada</div>
            <div class="recipient">{name}</div>
            <div class="desc">
                Atas partisipasi aktifnya sebagai {peserta_or_narasumber} dalam kegiatan komunitas PalembangPy yang bertajuk<br>
                <span class="event-name">"{event_title}"</span><br>
                yang diselenggarakan pada tanggal {date_str}.
            </div>
        </div>

        <div class="footer">
            <div class="left-footer">
                <div class="qr-box">
                    <svg viewBox="0 0 25 25" width="65" height="65">
                        <path d="M0 0h9v9H0zM16 0h9v9H16zM0 16h9v9H0z" fill="#000"/>
                        <rect x="3" y="3" width="3" height="3" fill="#fff"/>
                        <rect x="19" y="3" width="3" height="3" fill="#fff"/>
                        <rect x="3" y="19" width="3" height="3" fill="#fff"/>
                        <rect x="11" y="2" width="2" height="5" fill="#000"/>
                        <rect x="2" y="11" width="5" height="2" fill="#000"/>
                        <rect x="11" y="11" width="3" height="3" fill="#000"/>
                        <rect x="16" y="11" width="7" height="2" fill="#000"/>
                        <rect x="11" y="16" width="2" height="7" fill="#000"/>
                        <rect x="16" y="16" width="3" height="3" fill="#000"/>
                        <rect x="21" y="16" width="2" height="7" fill="#000"/>
                        <rect x="16" y="21" width="4" height="2" fill="#000"/>
                    </svg>
                </div>
                <div class="cert-info">
                    <span class="verify-text">Scan untuk Verifikasi</span>
                    <span class="cert-id">ID: {cert_id}</span>
                    <span class="cert-id">NIM: {nim}</span>
                </div>
            </div>
            <div class="signature-box">
                <strong>Lead PalembangPy Community</strong>
            </div>
        </div>
    </div>
</body>
</html>"""

@require_admin
async def generate_user_certificate(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args
    if len(args) < 3:
        await update.message.reply_text("⚠️ Format salah! Gunakan: `/cert [telegram_id] [event_id] [peserta|narasumber]`", parse_mode="Markdown")
        return

    tg_id, event_id, role_type = args[0], args[1], args[2]
    peserta_or_narasumber = "narasumber" if role_type.lower() == "narasumber" else "peserta"

    with Session(engine) as db:
        user = db.exec(select(User).where(User.telegram_id == tg_id, User.deleted_at == None)).first()
        event = db.get(Event, event_id)

        if not user or not event:
            await update.message.reply_text("❌ User atau Event tidak ditemukan di database.")
            return

        date_str = event.date.strftime("%d %B %Y") if isinstance(event.date, datetime) else str(event.date)
        cert_id = f"PPY-{event.id[:4].upper()}-{user.telegram_id[-4:]}"
        nim = getattr(user, "member_code", "-") or "-"

        html_content = generate_certificate_html(
            name=user.name.title(),
            peserta_or_narasumber=peserta_or_narasumber,
            event_title=event.title,
            date_str=date_str,
            cert_id=cert_id,
            nim=nim
        )

        file_path = f"/tmp/certificate_{user.telegram_id}.html"
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(html_content)

        with open(file_path, "rb") as f:
            await update.message.reply_document(
                document=InputFile(f, filename=f"Sertifikat_{user.name}.html"),
                caption=f"✅ Sertifikat untuk *{user.name}* berhasil digenerate!",
                parse_mode="Markdown"
            )

        if os.path.exists(file_path):
            os.remove(file_path)

async def auto_generate_event_certificates(context: ContextTypes.DEFAULT_TYPE):
    now = datetime.now(JAKARTA_TZ)
    with Session(engine) as db:
        events = db.exec(select(Event).where(Event.deleted_at == None)).all()
        for event in events:
            if event.date and isinstance(event.date, datetime):
                event_dt = event.date if event.date.tzinfo else event.date.replace(tzinfo=JAKARTA_TZ)
                if event_dt < now and not getattr(event, "certificates_sent", False):
                    event.certificates_sent = True
                    db.add(event)
                    db.commit()
