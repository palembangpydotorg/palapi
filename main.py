from contextlib import asynccontextmanager
from datetime import timedelta
from uuid import UUID
from typing import Annotated
import hashlib
import hmac
import json
import os
from urllib.parse import parse_qsl

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Query, Depends, UploadFile, File, Form, Request, status
from fastapi.security import OAuth2PasswordRequestForm
from fastapi.middleware.cors import CORSMiddleware
from sqlmodel import Session, select
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from jose import JWTError, jwt
from pydantic import BaseModel

from telegram import Update, Bot
from telegram.ext import Application

from database import init_db, get_session
from models import User
from crud import verify_password
import schemas
import crud

load_dotenv()

# --- Config & Environment ---
SECRET_KEY = os.getenv("SECRET_KEY", "CHANGE_THIS_TO_STRONG_SECRET_KEY_IN_PRODUCTION")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24 * 7
BOT_TOKEN = os.getenv("BOT_TOKEN", "")
WEBHOOK_URL = os.getenv("WEBHOOK_URL", "")


class Token(BaseModel):
    access_token: str
    token_type: str


class TelegramAuthRequest(BaseModel):
    init_data: str


class EventRegisterRequest(BaseModel):
    user_id: UUID


def create_access_token(data: dict, expires_delta: timedelta | None = None) -> str:
    from datetime import datetime, timezone, timedelta as td
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + td(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def verify_telegram_init_data(init_data: str) -> dict | None:
    if not BOT_TOKEN:
        return None
    parsed = dict(parse_qsl(init_data))
    hash_received = parsed.pop("hash", None)
    if not hash_received:
        return None
    data_check_string = "\n".join(f"{k}={v}" for k, v in sorted(parsed.items()))
    secret_key = hmac.new(b"WebAppData", BOT_TOKEN.encode(), hashlib.sha256).digest()
    computed_hash = hmac.new(secret_key, data_check_string.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(computed_hash, hash_received):
        return None
    from datetime import datetime, timezone
    auth_date = int(parsed.get("auth_date", 0))
    if (datetime.now(timezone.utc).timestamp() - auth_date) > 86400:
        return None
    user_str = parsed.get("user", "{}")
    try:
        return json.loads(user_str)
    except json.JSONDecodeError:
        return None


async def get_current_user(
    request: Request,
    db: Annotated[Session, Depends(get_session)]
) -> User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        raise credentials_exception
    token = auth_header.split(" ")[1]

    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id_str: str | None = payload.get("sub")
        if user_id_str is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception

    from uuid import UUID
    try:
        user_id_obj = UUID(user_id_str)
    except ValueError:
        raise credentials_exception

    user = db.exec(select(User).where(User.id == user_id_obj, User.deleted_at == None)).first()

    if user is None:
        raise credentials_exception
    return user


# --- App Setup ---
limiter = Limiter(key_func=get_remote_address)
DB = Annotated[Session, Depends(get_session)]
CurrentUser = Annotated[User, Depends(get_current_user)]


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()

    if BOT_TOKEN:
        tg_app = Application.builder().token(BOT_TOKEN).build()
        
        from bot.handlers import setup_handlers
        setup_handlers(tg_app)
        
        await tg_app.initialize()
        
        if WEBHOOK_URL:
            webhook_endpoint = f"{WEBHOOK_URL.rstrip('/')}/v1/webhook/telegram"
            await tg_app.bot.set_webhook(url=webhook_endpoint)
            print(f"🔗 Telegram Webhook successfully set to: {webhook_endpoint}")
            
        await tg_app.start()
        app.state.tg_app = tg_app

    yield

    if BOT_TOKEN and hasattr(app.state, "tg_app"):
        await app.state.tg_app.stop()
        await app.state.tg_app.shutdown()


app = FastAPI(
    title="PalembangPy Community API & Webhook",
    version="1.2.0",
    description="Production-ready FastAPI backend with Telegram Webhook & full features",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"]
)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)


# ==========================================
# --- TELEGRAM WEBHOOK ENDPOINT ---
# ==========================================
@app.post("/v1/webhook/telegram")
async def telegram_webhook(request: Request):
    if not hasattr(app.state, "tg_app"):
        raise HTTPException(status_code=503, detail="Telegram bot is not initialized")
    
    try:
        data = await request.json()
        update = Update.de_json(data, app.state.tg_app.bot)
        await app.state.tg_app.process_update(update)
        return {"status": "ok"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


# ==========================================
# --- WEB INBOX ENDPOINTS (CONTACT & CHAT) --
# ==========================================
def escape_markdown_v2(text: str) -> str:
    return str(text or '').replace('_','\\_').replace('*','\\*').replace('[','\\[').replace(']','\\]').replace('(','\\(').replace(')','\\)').replace('~','\\~').replace('`','\\`').replace('>','\\>').replace('#','\\#').replace('+','\\+').replace('-','\\-').replace('=','\\=').replace('|','\\|').replace('{','\\{').replace('}','\\}').replace('.','\\.').replace('!','\\!')

@app.post("/v1/contact")
@limiter.limit("10/minute")
async def submit_contact_form(request: Request, data: schemas.ContactFormRequest):
    inbox_chat_id = os.getenv("INBOX_CHAT_ID") or os.getenv("GROUP_CHAT_ID")
    if not BOT_TOKEN or not inbox_chat_id:
        raise HTTPException(status_code=500, detail="Telegram Bot Token atau Inbox Chat ID belum dikonfigurasi.")

    telegram_text = (
        f"*Eeeh Bang, Ada Pesan Masuk Dari Kontak Nih\\!*\n\n"
        f"*Nama Pengirim:* {escape_markdown_v2(data.name)}\n"
        f"*Email Pengirim:* {escape_markdown_v2(data.email)}\n"
        f"*Perihal Pengirim:* {escape_markdown_v2(data.subject)}\n\n"
        f"*Isi Pesannya:*\n> {escape_markdown_v2(data.message)}"
    )

    bot = Bot(token=BOT_TOKEN)
    try:
        await bot.send_message(chat_id=inbox_chat_id, text=telegram_text, parse_mode="MarkdownV2")
        return {"status": "success", "message": "Pesan berhasil dikirim ke pengurus."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Gagal mengirim ke Telegram: {str(e)}")

@app.post("/v1/chat")
@limiter.limit("30/minute")
async def submit_chat_widget(request: Request, data: schemas.ChatWidgetRequest):
    inbox_chat_id = os.getenv("INBOX_CHAT_ID") or os.getenv("GROUP_CHAT_ID")
    if not BOT_TOKEN or not inbox_chat_id:
        raise HTTPException(status_code=500, detail="Konfigurasi Telegram belum lengkap.")

    telegram_text = (
        f"*💬 Pesan Baru dari Web Chat Widget\\!*\n\n"
        f"*Isi Pesan:*\n> {escape_markdown_v2(data.message)}"
    )

    bot = Bot(token=BOT_TOKEN)
    try:
        await bot.send_message(chat_id=inbox_chat_id, text=telegram_text, parse_mode="MarkdownV2")
        
        normalized = data.message.lower()
        if any(k in normalized for k in ['event', 'acara', 'workshop', 'meetup']):
            reply = 'Untuk jadwal kegiatan bisa dilihat di halaman Event. Pesan Anda telah diteruskan ke PalembangPy Inbox.'
        elif any(k in normalized for k in ['project', 'proyek', 'github']):
            reply = 'Kamu bisa melihat karya komunitas di halaman Project. Pesan Anda sudah diteruskan ke pengurus.'
        elif any(k in normalized for k in ['kontak', 'email', 'kerja sama', 'kerjasama']):
            reply = 'Silakan gunakan formulir pada halaman Kontak. Pesan Anda sudah masuk ke inbox pengurus.'
        else:
            reply = 'Pesan diterima dan telah diteruskan ke grup PalembangPy Inbox. Terima kasih sudah menyapa!'

        return {"status": "success", "reply": reply}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Gagal memproses chat: {str(e)}")


# --- Auth ---
@app.post("/v1/auth/login", response_model=Token)
def login(
    *,
    request: Request,
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: DB
):
    user = db.exec(select(User).where(
        (User.username == form_data.username) | (User.telegram_id == form_data.username),
        User.deleted_at == None
    )).first()
    if not user or not verify_password(form_data.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username/telegram_id or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": str(user.id)}, expires_delta=access_token_expires
    )
    return {"access_token": access_token, "token_type": "bearer"}


@app.post("/v1/auth/telegram", response_model=Token)
@limiter.limit("30/minute")
def auth_via_telegram(
    *,
    request: Request,
    data: TelegramAuthRequest,
    db: DB
):
    tg_user = verify_telegram_init_data(data.init_data)
    if not tg_user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid Telegram init data"
        )

    telegram_id = str(tg_user.get("id"))
    user = db.exec(select(User).where(
        User.telegram_id == telegram_id,
        User.deleted_at == None
    )).first()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not registered. Please register via Telegram bot first."
        )

    access_token = create_access_token(
        data={"sub": str(user.id)},
        expires_delta=timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    return {"access_token": access_token, "token_type": "bearer"}


@app.get("/v1/auth/me")
def get_my_profile(
    *,
    request: Request,
    current_user: CurrentUser
):
    return schemas.UserResponse.model_validate(current_user)


# --- User Endpoints ---
@app.get("/v1/users", response_model=list[schemas.UserResponse])
@limiter.limit("60/minute")
def list_users(
    *,
    request: Request,
    db: DB,
    current_user: CurrentUser,
    include_deleted: bool = Query(False)
):
    return crud.get_users(db, include_deleted=include_deleted)


@app.post("/v1/users", response_model=schemas.UserCreateResponse, status_code=201)
@limiter.limit("20/minute")
def create_user(
    *,
    request: Request,
    data: schemas.UserCreate,
    db: DB
):
    try:
        user, plain_password = crud.create_user(db, data.model_dump())
        user_data = schemas.UserResponse.model_validate(user).model_dump()
        return schemas.UserCreateResponse(**user_data, generated_password=plain_password)
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))


@app.get("/v1/users/{user_id}", response_model=schemas.UserResponse)
@limiter.limit("60/minute")
def get_user(
    *,
    request: Request,
    user_id: UUID,
    db: DB,
    current_user: CurrentUser,
    include_deleted: bool = Query(False)
):
    user = crud.get_user(db, user_id, include_deleted=include_deleted)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user


@app.get("/v1/users/telegram/{telegram_id}", response_model=schemas.UserResponse)
@limiter.limit("30/minute")
def get_user_by_telegram_id(
    *,
    request: Request,
    telegram_id: str,
    db: DB,
    current_user: CurrentUser
):
    user = crud.get_user_by_telegram(db, telegram_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user


@app.patch("/v1/users/{user_id}", response_model=schemas.UserResponse)
@limiter.limit("30/minute")
def update_user_info(
    *,
    request: Request,
    user_id: UUID,
    data: schemas.UserUpdate,
    db: DB,
    current_user: CurrentUser
):
    user = crud.get_user(db, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return crud.update_user(db, user, data.model_dump(exclude_unset=True))


@app.delete("/v1/users/{user_id}/soft")
@limiter.limit("15/minute")
def soft_delete_user_account(
    *,
    request: Request,
    user_id: UUID,
    db: DB,
    current_user: CurrentUser
):
    user = crud.get_user(db, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    crud.soft_delete_user(db, user)
    return {"status": "success", "message": "Account soft deleted"}


@app.delete("/v1/users/{user_id}/hard")
@limiter.limit("10/minute")
def hard_delete_user_account(
    *,
    request: Request,
    user_id: UUID,
    db: DB,
    current_user: CurrentUser
):
    user = crud.get_user(db, user_id, include_deleted=True)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    crud.hard_delete_user(db, user)
    return {"status": "success", "message": "Account permanently deleted"}


@app.get("/v1/users/{user_id}/certificates", response_model=list[schemas.CertificateResponse])
@limiter.limit("30/minute")
def list_user_certificates(
    *,
    request: Request,
    user_id: UUID,
    db: DB,
    current_user: CurrentUser
):
    return crud.get_certificates_by_user(db, user_id)


@app.get("/v1/users/{user_id}/events")
@limiter.limit("30/minute")
def list_user_events(
    *,
    request: Request,
    user_id: UUID,
    db: DB,
    current_user: CurrentUser
):
    return crud.get_user_events(db, user_id)


# --- Partner Endpoints ---
@app.get("/v1/partners", response_model=list[schemas.PartnerResponse])
@limiter.limit("60/minute")
def list_partners(
    *,
    request: Request,
    db: DB,
    current_user: CurrentUser,
    include_deleted: bool = Query(False)
):
    return crud.get_partners(db, include_deleted=include_deleted)


@app.post("/v1/partners", response_model=schemas.PartnerResponse, status_code=201)
@limiter.limit("20/minute")
def register_partner(
    *,
    request: Request,
    data: schemas.PartnerCreate,
    db: DB,
    current_user: CurrentUser
):
    return crud.create_partner(db, data.model_dump())


@app.get("/v1/partners/{partner_id}", response_model=schemas.PartnerResponse)
@limiter.limit("60/minute")
def get_partner_info(
    *,
    request: Request,
    partner_id: UUID,
    db: DB,
    current_user: CurrentUser,
    include_deleted: bool = Query(False)
):
    partner = crud.get_partner(db, partner_id, include_deleted=include_deleted)
    if not partner:
        raise HTTPException(status_code=404, detail="Partner not found")
    return partner


@app.patch("/v1/partners/{partner_id}", response_model=schemas.PartnerResponse)
@limiter.limit("30/minute")
def update_partner_info(
    *,
    request: Request,
    partner_id: UUID,
    data: schemas.PartnerUpdate,
    db: DB,
    current_user: CurrentUser
):
    partner = crud.get_partner(db, partner_id)
    if not partner:
        raise HTTPException(status_code=404, detail="Partner not found")
    return crud.update_partner(db, partner, data.model_dump(exclude_unset=True))


@app.delete("/v1/partners/{partner_id}/soft")
@limiter.limit("15/minute")
def soft_delete_partner_info(
    *,
    request: Request,
    partner_id: UUID,
    db: DB,
    current_user: CurrentUser
):
    partner = crud.get_partner(db, partner_id)
    if not partner:
        raise HTTPException(status_code=404, detail="Partner not found")
    crud.soft_delete_partner(db, partner)
    return {"status": "success", "message": "Partner soft deleted"}


@app.delete("/v1/partners/{partner_id}/hard")
@limiter.limit("10/minute")
def hard_delete_partner_info(
    *,
    request: Request,
    partner_id: UUID,
    db: DB,
    current_user: CurrentUser
):
    partner = crud.get_partner(db, partner_id, include_deleted=True)
    if not partner:
        raise HTTPException(status_code=404, detail="Partner not found")
    crud.hard_delete_partner(db, partner)
    return {"status": "success", "message": "Partner permanently deleted"}


# --- Event Endpoints ---
@app.get("/v1/events", response_model=list[schemas.EventResponse])
@limiter.limit("120/minute")
def list_events(
    *,
    request: Request,
    db: DB,
    include_deleted: bool = Query(False)
):
    return crud.get_events(db, include_deleted=include_deleted)


@app.post("/v1/events", response_model=schemas.EventResponse, status_code=201)
@limiter.limit("20/minute")
def create_event_record(
    *,
    request: Request,
    data: schemas.EventCreate,
    db: DB,
    current_user: CurrentUser
):
    return crud.create_event(db, data.model_dump())


@app.get("/v1/events/{event_id}", response_model=schemas.EventResponse)
@limiter.limit("60/minute")
def get_event_detail(
    *,
    request: Request,
    event_id: UUID,
    db: DB,
    current_user: CurrentUser,
    include_deleted: bool = Query(False)
):
    event = crud.get_event(db, event_id, include_deleted=include_deleted)
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")
    return event


@app.patch("/v1/events/{event_id}", response_model=schemas.EventResponse)
@limiter.limit("30/minute")
def update_event_detail(
    *,
    request: Request,
    event_id: UUID,
    data: schemas.EventUpdate,
    db: DB,
    current_user: CurrentUser
):
    event = crud.get_event(db, event_id)
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")
    return crud.update_event(db, event, data.model_dump(exclude_unset=True))


@app.delete("/v1/events/{event_id}/soft")
@limiter.limit("15/minute")
def soft_delete_event_record(
    *,
    request: Request,
    event_id: UUID,
    db: DB,
    current_user: CurrentUser
):
    event = crud.get_event(db, event_id)
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")
    crud.soft_delete_event(db, event)
    return {"status": "success", "message": "Event soft deleted"}


@app.delete("/v1/events/{event_id}/hard")
@limiter.limit("10/minute")
def hard_delete_event_record(
    *,
    request: Request,
    event_id: UUID,
    db: DB,
    current_user: CurrentUser
):
    event = crud.get_event(db, event_id, include_deleted=True)
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")
    crud.hard_delete_event(db, event)
    return {"status": "success", "message": "Event permanently deleted"}


@app.post("/v1/events/{event_id}/register", status_code=201)
@limiter.limit("20/minute")
def register_for_event(
    *,
    request: Request,
    event_id: UUID,
    data: EventRegisterRequest,
    db: DB,
    current_user: CurrentUser
):
    event = crud.get_event(db, event_id)
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")
    user = crud.get_user(db, data.user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    try:
        reg = crud.register_user_to_event(db, data.user_id, event_id)
    except ValueError:
        raise HTTPException(status_code=409, detail="User already registered for this event")
    return {"status": "success", "registration_id": str(reg.id), "event_id": str(event_id), "user_id": str(data.user_id)}


@app.get("/v1/events/{event_id}/registrations")
@limiter.limit("30/minute")
def list_event_registrations(
    *,
    request: Request,
    event_id: UUID,
    db: DB,
    current_user: CurrentUser
):
    event = crud.get_event(db, event_id)
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")
    return crud.get_event_registrations(db, event_id)


@app.post("/v1/events/{event_id}/gencert", status_code=201)
@limiter.limit("10/minute")
def gencert(
    *,
    request: Request,
    event_id: UUID,
    data: schemas.CertificateGenerate,
    db: DB,
    current_user: CurrentUser
):
    event = crud.get_event(db, event_id)
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")
    results = []
    for user_id_str in data.user_ids:
        try:
            user_id = UUID(user_id_str)
            user = crud.get_user(db, user_id)
            if not user:
                continue
            cert = crud.create_certificate(
                db=db,
                user_id=user_id,
                event_id=event_id,
                recipient_name=user.name,
                event_name=event.title,
                role=data.role,
                issued_by=user_id
            )
            results.append({"code": cert.code, "recipient": cert.recipient_name})
        except Exception:
            continue
    return {"status": "success", "generated_count": len(results), "data": results}


# --- Speaker Endpoints ---
@app.get("/v1/speakers", response_model=list[schemas.SpeakerResponse])
@limiter.limit("60/minute")
def list_speakers(
    *,
    request: Request,
    db: DB,
    include_deleted: bool = Query(False)
):
    return crud.get_speakers(db, include_deleted=include_deleted)


@app.post("/v1/speakers", response_model=schemas.SpeakerResponse, status_code=201)
@limiter.limit("20/minute")
def register_speaker(
    *,
    request: Request,
    data: schemas.SpeakerCreate,
    db: DB,
    current_user: CurrentUser
):
    return crud.create_speaker(db, data.model_dump())


@app.get("/v1/speakers/{speaker_id}", response_model=schemas.SpeakerResponse)
@limiter.limit("60/minute")
def get_speaker_detail(
    *,
    request: Request,
    speaker_id: UUID,
    db: DB,
    current_user: CurrentUser,
    include_deleted: bool = Query(False)
):
    speaker = crud.get_speaker(db, speaker_id, include_deleted=include_deleted)
    if not speaker:
        raise HTTPException(status_code=404, detail="Speaker not found")
    return speaker


@app.patch("/v1/speakers/{speaker_id}", response_model=schemas.SpeakerResponse)
@limiter.limit("30/minute")
def update_speaker_detail(
    *,
    request: Request,
    speaker_id: UUID,
    data: schemas.SpeakerUpdate,
    db: DB,
    current_user: CurrentUser
):
    speaker = crud.get_speaker(db, speaker_id)
    if not speaker:
        raise HTTPException(status_code=404, detail="Speaker not found")
    return crud.update_speaker(db, speaker, data.model_dump(exclude_unset=True))


@app.delete("/v1/speakers/{speaker_id}/soft")
@limiter.limit("15/minute")
def soft_delete_speaker_record(
    *,
    request: Request,
    speaker_id: UUID,
    db: DB,
    current_user: CurrentUser
):
    speaker = crud.get_speaker(db, speaker_id)
    if not speaker:
        raise HTTPException(status_code=404, detail="Speaker not found")
    crud.soft_delete_speaker(db, speaker)
    return {"status": "success", "message": "Speaker soft deleted"}


@app.delete("/v1/speakers/{speaker_id}/hard")
@limiter.limit("10/minute")
def hard_delete_speaker_record(
    *,
    request: Request,
    speaker_id: UUID,
    db: DB,
    current_user: CurrentUser
):
    speaker = crud.get_speaker(db, speaker_id, include_deleted=True)
    if not speaker:
        raise HTTPException(status_code=404, detail="Speaker not found")
    crud.hard_delete_speaker(db, speaker)
    return {"status": "success", "message": "Speaker permanently deleted"}


@app.post("/v1/speakers/{speaker_id}/materials", status_code=201)
@limiter.limit("15/minute")
def upload_speaker_material(
    *,
    request: Request,
    speaker_id: UUID,
    title: Annotated[str, Form()],
    db: DB,
    current_user: CurrentUser,
    description: Annotated[str | None, Form()] = None,
    file: UploadFile = File(...)
):
    speaker = crud.get_speaker(db, speaker_id)
    if not speaker:
        raise HTTPException(status_code=404, detail="Speaker not found")
    crud.validate_file(file)
    saved_path = crud.save_uploaded_file(file, subfolder="speaker_materials")
    material = crud.create_speaker_material(
        db=db,
        speaker_id=speaker_id,
        title=title,
        description=description,
        file_path=str(saved_path),
        file_original_name=file.filename,
        file_mime_type=file.content_type,
        file_size=file.size or 0
    )
    return {
        "status": "success",
        "id": str(material.id),
        "file_path": material.file_path
    }


# --- Certificate Verification (Publik) ---
@app.get("/v1/certificates/verify/{code}", response_model=schemas.CertificateResponse)
@limiter.limit("120/minute")
def verify_certificate(
    *,
    request: Request,
    code: str,
    db: DB
):
    certificate = crud.get_certificate_by_code(db, code)
    if not certificate:
        raise HTTPException(status_code=404, detail="Certificate not found or revoked")
    return certificate


# --- Project Endpoints ---
@app.get("/v1/projects", response_model=list[schemas.ProjectResponse])
@limiter.limit("60/minute")
def list_projects(
    *,
    request: Request,
    db: DB,
    include_deleted: bool = Query(False),
    featured_only: bool = Query(False)
):
    return crud.get_projects(db, include_deleted=include_deleted, featured_only=featured_only)


@app.post("/v1/projects", response_model=schemas.ProjectResponse, status_code=201)
@limiter.limit("20/minute")
def create_project_record(
    *,
    request: Request,
    data: schemas.ProjectCreate,
    db: DB,
    current_user: CurrentUser
):
    return crud.create_project(db, data.model_dump())


@app.get("/v1/projects/{project_id}", response_model=schemas.ProjectResponse)
@limiter.limit("60/minute")
def get_project_detail(
    *,
    request: Request,
    project_id: UUID,
    db: DB,
    current_user: CurrentUser,
    include_deleted: bool = Query(False)
):
    project = crud.get_project(db, project_id, include_deleted=include_deleted)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return project


@app.patch("/v1/projects/{project_id}", response_model=schemas.ProjectResponse)
@limiter.limit("30/minute")
def update_project_detail(
    *,
    request: Request,
    project_id: UUID,
    data: schemas.ProjectUpdate,
    db: DB,
    current_user: CurrentUser
):
    project = crud.get_project(db, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return crud.update_project(db, project, data.model_dump(exclude_unset=True))


@app.delete("/v1/projects/{project_id}/soft")
@limiter.limit("15/minute")
def soft_delete_project_record(
    *,
    request: Request,
    project_id: UUID,
    db: DB,
    current_user: CurrentUser
):
    project = crud.get_project(db, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    crud.soft_delete_project(db, project)
    return {"status": "success", "message": "Project soft deleted"}


@app.delete("/v1/projects/{project_id}/hard")
@limiter.limit("10/minute")
def hard_delete_project_record(
    *,
    request: Request,
    project_id: UUID,
    db: DB,
    current_user: CurrentUser
):
    project = crud.get_project(db, project_id, include_deleted=True)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    crud.hard_delete_project(db, project)
    return {"status": "success", "message": "Project permanently deleted"}


# ==========================================
# --- PUBLIC STATS ENDPOINT ---
# ==========================================
@app.get("/v1/stats")
@limiter.limit("120/minute")
def public_stats(
    *,
    request: Request,
    db: DB
):
    from models import Event, Speaker, Project, User, Partner
    from sqlmodel import select

    users = db.exec(select(User).where(User.deleted_at == None)).all()
    events = db.exec(select(Event).where(Event.deleted_at == None)).all()
    speakers = db.exec(select(Speaker).where(Speaker.deleted_at == None)).all()
    partners = db.exec(select(Partner).where(Partner.deleted_at == None)).all()
    projects = db.exec(select(Project).where(Project.deleted_at == None, Project.status == "published")).all()

    admins = sum(1 for u in users if u.is_admin)
    staffs = sum(1 for u in users if u.is_staff and not u.is_admin)

    return {
        "members": len(users),
        "admins": admins,
        "staffs": staffs,
        "events": len(events),
        "speakers": len(speakers),
        "partners": len(partners),
        "projects": len(projects)
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=False)
