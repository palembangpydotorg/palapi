from datetime import datetime
from typing import Optional
from uuid import UUID
from pydantic import BaseModel, ConfigDict, field_validator, Field
import re

def convert_uuid(v):
    return str(v) if isinstance(v, UUID) else v

def sanitize_string(value: str, min_length: int = 1, max_length: int = 255) -> str:
    if not value or not value.strip():
        raise ValueError("Field cannot be empty")
    value = value.strip()
    if len(value) < min_length:
        raise ValueError(f"Minimum length is {min_length} characters")
    if len(value) > max_length:
        raise ValueError(f"Maximum length is {max_length} characters")
    return value

TELEGRAM_ID_PATTERN = re.compile(r'^[a-zA-Z0-9_-]+$')

# === USER ===
class UserBase(BaseModel):
    name: str = Field(..., min_length=2, max_length=100)
    username: str = Field(..., min_length=2, max_length=100)
    telegram_id: Optional[str] = Field(None, max_length=50)
    avatar_url: Optional[str] = Field(None, max_length=255)
    bio: Optional[str] = Field(None, max_length=500)
    instagram_url: Optional[str] = Field(None, max_length=255)
    twitter_url: Optional[str] = Field(None, max_length=255)
    linkedin_url: Optional[str] = Field(None, max_length=255)
    github_url: Optional[str] = Field(None, max_length=255)
    website_url: Optional[str] = Field(None, max_length=255)
    is_admin: bool = False
    is_staff: bool = False
    points: int = Field(0, ge=0)

    @field_validator("name", "username")
    def clean_string_fields(cls, value):
        return sanitize_string(value)

    @field_validator("telegram_id")
    def validate_telegram_id(cls, value):
        if value and not TELEGRAM_ID_PATTERN.match(value):
            raise ValueError("Invalid telegram_id format")
        return value

class UserCreate(UserBase):
    pass

# ✅ DIGUNAKAN: GET daftar, GET detail — TANPA password
class UserResponse(UserBase):
    model_config = ConfigDict(from_attributes=True)
    id: str
    member_code: str
    created_at: datetime
    deleted_at: Optional[datetime] = None
    _convert_id = field_validator("id", mode="before")(convert_uuid)

# ✅ DIGUNAKAN: HANYA POST pendaftaran — DENGAN password sekali
class UserCreateResponse(UserResponse):
    generated_password: str

class UserUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=2, max_length=100)
    username: Optional[str] = Field(None, min_length=2, max_length=100)
    telegram_id: Optional[str] = Field(None, max_length=50)
    avatar_url: Optional[str] = Field(None, max_length=255)
    bio: Optional[str] = Field(None, max_length=500)
    instagram_url: Optional[str] = Field(None, max_length=255)
    twitter_url: Optional[str] = Field(None, max_length=255)
    linkedin_url: Optional[str] = Field(None, max_length=255)
    github_url: Optional[str] = Field(None, max_length=255)
    website_url: Optional[str] = Field(None, max_length=255)
    is_admin: Optional[bool] = None
    is_staff: Optional[bool] = None
    points: Optional[int] = Field(None, ge=0)

    @field_validator("name", "username")
    def clean_string_fields(cls, value):
        return sanitize_string(value) if value else value

    @field_validator("telegram_id")
    def validate_telegram_id(cls, value):
        if value and not TELEGRAM_ID_PATTERN.match(value):
            raise ValueError("Invalid telegram_id format")
        return value

# === PARTNER ===
class PartnerBase(BaseModel):
    name: str = Field(..., min_length=2, max_length=100)
    type: Optional[str] = Field(None, max_length=50)
    contact: Optional[str] = Field(None, max_length=100)
    logo_url: Optional[str] = Field(None, max_length=255)
    website_url: Optional[str] = Field(None, max_length=255)
    description: Optional[str] = None

class PartnerCreate(PartnerBase):
    pass

class PartnerUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=2, max_length=100)
    type: Optional[str] = Field(None, max_length=50)
    contact: Optional[str] = Field(None, max_length=100)
    logo_url: Optional[str] = Field(None, max_length=255)
    website_url: Optional[str] = Field(None, max_length=255)
    description: Optional[str] = None

class PartnerResponse(PartnerBase):
    model_config = ConfigDict(from_attributes=True)
    id: str
    created_at: datetime
    deleted_at: Optional[datetime] = None
    _convert_id = field_validator("id", mode="before")(convert_uuid)

# === EVENT ===
class EventBase(BaseModel):
    title: str = Field(..., min_length=3, max_length=200)
    description: Optional[str] = None
    location: Optional[str] = Field(None, max_length=200)
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None

class EventCreate(EventBase):
    pass

class EventUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=3, max_length=200)
    description: Optional[str] = None
    location: Optional[str] = Field(None, max_length=200)
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None

class EventResponse(EventBase):
    model_config = ConfigDict(from_attributes=True)
    id: str
    created_at: datetime
    deleted_at: Optional[datetime] = None
    _convert_id = field_validator("id", mode="before")(convert_uuid)

# === SPEAKER ===
class SpeakerBase(BaseModel):
    user_id: str
    event_id: str
    topic: Optional[str] = Field(None, max_length=200)
    bio: Optional[str] = None

class SpeakerCreate(SpeakerBase):
    pass

class SpeakerUpdate(BaseModel):
    topic: Optional[str] = Field(None, max_length=200)
    bio: Optional[str] = None

class SpeakerResponse(SpeakerBase):
    model_config = ConfigDict(from_attributes=True)
    id: str
    created_at: datetime
    deleted_at: Optional[datetime] = None
    user: Optional[UserResponse] = None
    event: Optional[EventResponse] = None
    _convert_all = field_validator("id", "user_id", "event_id", mode="before")(convert_uuid)

# === SPEAKER MATERIAL ===
class SpeakerMaterialBase(BaseModel):
    title: str = Field(..., min_length=2, max_length=200)
    description: Optional[str] = None

class SpeakerMaterialResponse(SpeakerMaterialBase):
    model_config = ConfigDict(from_attributes=True)
    id: str
    speaker_id: str
    file_path: str
    file_original_name: str
    file_mime_type: str
    file_size: int
    created_at: datetime
    _convert_all = field_validator("id", "speaker_id", mode="before")(convert_uuid)

# === CERTIFICATE ===
class CertificateGenerate(BaseModel):
    user_ids: list[str]
    role: str = Field("Participant", max_length=50)

class CertificateResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    code: str
    user_id: str
    event_id: str
    speaker_id: Optional[str] = None
    recipient_name: str
    event_name: str
    role: str
    file_path: str
    created_at: datetime
    _convert_all = field_validator(
        "id", "user_id", "event_id", "speaker_id", mode="before"
    )(convert_uuid)