from uuid import UUID, uuid4
from pathlib import Path
from datetime import datetime
from typing import Any, Tuple
from sqlmodel import Session, select
from fastapi import UploadFile, HTTPException
import secrets
import string
import bcrypt

from models import (
    User, Partner, Event, Speaker,
    SpeakerMaterial, Certificate
)


# --- Security ---
def get_password_hash(password: str) -> str:
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(password.encode("utf-8"), salt)
    return hashed.decode("utf-8")

def generate_secure_password(length: int = 12) -> str:
    return "".join(secrets.choice(string.ascii_letters + string.digits) for _ in range(length))

# --- Configuration ---
UPLOAD_DIR = Path("uploads")
UPLOAD_DIR.mkdir(exist_ok=True)
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB
ALLOWED_MIME_TYPES = {
    "application/pdf",
    "image/png",
    "image/jpeg",
    "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    "application/zip"
}


# --- Helpers ---
def exclude_deleted(model: Any):
    return model.deleted_at.is_(None)


def validate_file(file: UploadFile):
    if file.size and file.size > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=400,
            detail=f"File too large. Maximum allowed: {MAX_FILE_SIZE // 1024 // 1024} MB"
        )
    if file.content_type not in ALLOWED_MIME_TYPES:
        raise HTTPException(
            status_code=400,
            detail="File type not allowed. Allowed types: PDF, PNG, JPEG, PPTX, ZIP"
        )


def save_uploaded_file(file: UploadFile, subfolder: str) -> Path:
    ext = file.filename.split(".")[-1].lower()
    safe_name = f"{uuid4()}.{ext}"
    target = UPLOAD_DIR / subfolder / safe_name
    target.parent.mkdir(exist_ok=True)
    with target.open("wb") as f:
        f.write(file.file.read())
    return target


# --- User ---
def create_user(db: Session, data: dict) -> Tuple[User, str]:
    if data.get("telegram_id"):
        existing = db.exec(
            select(User).where(User.telegram_id == data["telegram_id"])
        ).first()
        if existing:
            raise ValueError("telegram_id already registered")

    generated_password = generate_secure_password()  # Default 12 chars
    data["password_hash"] = get_password_hash(generated_password)

    user = User(**data)
    db.add(user)
    db.commit()
    db.refresh(user)
    return user, generated_password


def get_users(db: Session, include_deleted: bool = False) -> list[User]:
    stmt = select(User)
    if not include_deleted:
        stmt = stmt.where(exclude_deleted(User))
    return db.exec(stmt.order_by(User.created_at.desc())).all()


def get_user(db: Session, user_id: UUID, include_deleted: bool = False) -> User | None:
    stmt = select(User).where(User.id == user_id)
    if not include_deleted:
        stmt = stmt.where(exclude_deleted(User))
    return db.exec(stmt).first()


def get_user_by_telegram(db: Session, telegram_id: str) -> User | None:
    return db.exec(
        select(User).where(
            User.telegram_id == telegram_id,
            exclude_deleted(User)
        )
    ).first()


def update_user(db: Session, user: User, data: dict) -> User:
    for key, value in data.items():
        if value is not None:
            setattr(user, key, value)
    db.commit()
    db.refresh(user)
    return user


def soft_delete_user(db: Session, user: User) -> bool:
    user.soft_delete()
    db.commit()
    return True


def hard_delete_user(db: Session, user: User) -> bool:
    db.delete(user)
    db.commit()
    return True


# --- Partner ---
def create_partner(db: Session, data: dict) -> Partner:
    partner = Partner(**data)
    db.add(partner)
    db.commit()
    db.refresh(partner)
    return partner


def get_partners(db: Session, include_deleted: bool = False) -> list[Partner]:
    stmt = select(Partner)
    if not include_deleted:
        stmt = stmt.where(exclude_deleted(Partner))
    return db.exec(stmt.order_by(Partner.created_at.desc())).all()


def get_partner(db: Session, partner_id: UUID, include_deleted: bool = False) -> Partner | None:
    stmt = select(Partner).where(Partner.id == partner_id)
    if not include_deleted:
        stmt = stmt.where(exclude_deleted(Partner))
    return db.exec(stmt).first()


def update_partner(db: Session, partner: Partner, data: dict) -> Partner:
    for key, value in data.items():
        if value is not None:
            setattr(partner, key, value)
    db.commit()
    db.refresh(partner)
    return partner


def soft_delete_partner(db: Session, partner: Partner) -> bool:
    partner.soft_delete()
    db.commit()
    return True


def hard_delete_partner(db: Session, partner: Partner) -> bool:
    db.delete(partner)
    db.commit()
    return True


# --- Event ---
def create_event(db: Session, data: dict) -> Event:
    event = Event(**data)
    db.add(event)
    db.commit()
    db.refresh(event)
    return event


def get_events(db: Session, include_deleted: bool = False) -> list[Event]:
    stmt = select(Event)
    if not include_deleted:
        stmt = stmt.where(exclude_deleted(Event))
    return db.exec(stmt.order_by(Event.created_at.desc())).all()


def get_event(db: Session, event_id: UUID, include_deleted: bool = False) -> Event | None:
    stmt = select(Event).where(Event.id == event_id)
    if not include_deleted:
        stmt = stmt.where(exclude_deleted(Event))
    return db.exec(stmt).first()


def update_event(db: Session, event: Event, data: dict) -> Event:
    for key, value in data.items():
        if value is not None:
            setattr(event, key, value)
    db.commit()
    db.refresh(event)
    return event


def soft_delete_event(db: Session, event: Event) -> bool:
    event.soft_delete()
    db.commit()
    return True


def hard_delete_event(db: Session, event: Event) -> bool:
    db.delete(event)
    db.commit()
    return True


# --- Speaker ---
def create_speaker(db: Session, data: dict) -> Speaker:
    speaker = Speaker(**data)
    db.add(speaker)
    db.commit()
    db.refresh(speaker)
    return speaker


def get_speakers(db: Session, include_deleted: bool = False) -> list[Speaker]:
    stmt = select(Speaker)
    if not include_deleted:
        stmt = stmt.where(exclude_deleted(Speaker))
    return db.exec(stmt.order_by(Speaker.created_at.desc())).all()


def get_speaker(db: Session, speaker_id: UUID, include_deleted: bool = False) -> Speaker | None:
    stmt = select(Speaker).where(Speaker.id == speaker_id)
    if not include_deleted:
        stmt = stmt.where(exclude_deleted(Speaker))
    return db.exec(stmt).first()


def update_speaker(db: Session, speaker: Speaker, data: dict) -> Speaker:
    for key, value in data.items():
        if value is not None:
            setattr(speaker, key, value)
    db.commit()
    db.refresh(speaker)
    return speaker


def soft_delete_speaker(db: Session, speaker: Speaker) -> bool:
    speaker.soft_delete()
    db.commit()
    return True


def hard_delete_speaker(db: Session, speaker: Speaker) -> bool:
    db.delete(speaker)
    db.commit()
    return True


# --- Speaker Material ---
def create_speaker_material(
    db: Session,
    speaker_id: UUID,
    title: str,
    description: str | None,
    file_path: str,
    file_original_name: str,
    file_mime_type: str,
    file_size: int
) -> SpeakerMaterial:
    material = SpeakerMaterial(
        speaker_id=speaker_id,
        title=title,
        description=description,
        file_path=file_path,
        file_original_name=file_original_name,
        file_mime_type=file_mime_type,
        file_size=file_size
    )
    db.add(material)
    db.commit()
    db.refresh(material)
    return material


def get_materials_by_speaker(db: Session, speaker_id: UUID) -> list[SpeakerMaterial]:
    return db.exec(
        select(SpeakerMaterial)
        .where(
            SpeakerMaterial.speaker_id == speaker_id,
            exclude_deleted(SpeakerMaterial)
        )
        .order_by(SpeakerMaterial.created_at.desc())
    ).all()


# --- Certificate ---
def create_certificate(
    db: Session,
    user_id: UUID,
    event_id: UUID,
    recipient_name: str,
    event_name: str,
    role: str,
    issued_by: UUID,
    speaker_id: UUID | None = None
) -> Certificate:
    certificate = Certificate(
        user_id=user_id,
        event_id=event_id,
        speaker_id=speaker_id,
        recipient_name=recipient_name,
        event_name=event_name,
        role=role,
        file_path=f"/certificates/generated-{uuid4()}.pdf",
        issued_by=issued_by
    )
    db.add(certificate)
    db.commit()
    db.refresh(certificate)
    return certificate


def get_certificate_by_code(db: Session, code: str) -> Certificate | None:
    return db.exec(
        select(Certificate).where(
            Certificate.code == code,
            exclude_deleted(Certificate)
        )
    ).first()


def get_certificates_by_user(db: Session, user_id: UUID) -> list[Certificate]:
    return db.exec(
        select(Certificate)
        .where(
            Certificate.user_id == user_id,
            exclude_deleted(Certificate)
        )
        .order_by(Certificate.created_at.desc())
    ).all()