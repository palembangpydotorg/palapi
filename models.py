from datetime import datetime
from typing import Optional
from uuid import UUID, uuid4
from sqlmodel import Field, SQLModel, Relationship
from uuid_utils import uuid7
import zoneinfo

JAKARTA_TZ = zoneinfo.ZoneInfo("Asia/Jakarta")

def now_jakarta() -> datetime:
    return datetime.now(tz=JAKARTA_TZ)

def generate_member_code() -> str:
    now = now_jakarta()
    yy = now.strftime("%y")
    mm = now.strftime("%m")
    seq = str(uuid7().int % 1_000_000).zfill(6)
    return f"PALPY{yy}{mm}{seq}"


class SoftDeleteMixin(SQLModel):
    deleted_at: Optional[datetime] = Field(default=None, nullable=True)

    def soft_delete(self):
        self.deleted_at = now_jakarta()

    @property
    def is_deleted(self) -> bool:
        return self.deleted_at is not None


class User(SoftDeleteMixin, table=True):
    __tablename__ = "users"

    id: UUID = Field(default_factory=uuid7, primary_key=True)
    member_code: str = Field(
        default_factory=generate_member_code,
        unique=True, index=True, max_length=20
    )
    name: str = Field(nullable=False, max_length=100)
    username: str = Field(nullable=False, max_length=100, unique=True, index=True)
    telegram_id: Optional[str] = Field(
        default=None, unique=True, index=True, max_length=50
    )
    password_hash: Optional[str] = Field(default=None, max_length=255)
    avatar_url: Optional[str] = Field(default=None, max_length=255)
    bio: Optional[str] = Field(default=None, max_length=500)
    instagram_url: Optional[str] = Field(default=None, max_length=255)
    twitter_url: Optional[str] = Field(default=None, max_length=255)
    linkedin_url: Optional[str] = Field(default=None, max_length=255)
    github_url: Optional[str] = Field(default=None, max_length=255)
    website_url: Optional[str] = Field(default=None, max_length=255)
    is_admin: bool = Field(default=False, nullable=False)
    is_staff: bool = Field(default=False, nullable=False)
    points: int = Field(default=0, nullable=False)
    created_at: datetime = Field(default_factory=now_jakarta)

    speakers: list["Speaker"] = Relationship(back_populates="user")


class Partner(SoftDeleteMixin, table=True):
    __tablename__ = "partners"
    id: UUID = Field(default_factory=uuid7, primary_key=True)
    name: str = Field(nullable=False, max_length=100)
    type: Optional[str] = Field(default=None, max_length=50)
    contact: Optional[str] = Field(default=None, max_length=100)
    logo_url: Optional[str] = Field(default=None, max_length=255)
    website_url: Optional[str] = Field(default=None, max_length=255)
    description: Optional[str] = Field(default=None)
    created_at: datetime = Field(default_factory=now_jakarta)


class Event(SoftDeleteMixin, table=True):
    __tablename__ = "events"
    id: UUID = Field(default_factory=uuid7, primary_key=True)
    title: str = Field(nullable=False, max_length=200)
    description: Optional[str] = Field(default=None)
    location: Optional[str] = Field(default=None, max_length=200)
    start_time: Optional[datetime] = Field(default=None)
    end_time: Optional[datetime] = Field(default=None)
    created_at: datetime = Field(default_factory=now_jakarta)

    speakers: list["Speaker"] = Relationship(back_populates="event")


class Speaker(SoftDeleteMixin, table=True):
    __tablename__ = "speakers"
    id: UUID = Field(default_factory=uuid7, primary_key=True)
    user_id: UUID = Field(foreign_key="users.id")
    event_id: UUID = Field(foreign_key="events.id")
    topic: Optional[str] = Field(default=None, max_length=200)
    bio: Optional[str] = Field(default=None)
    created_at: datetime = Field(default_factory=now_jakarta)

    user: User = Relationship(back_populates="speakers")
    event: Event = Relationship(back_populates="speakers")
    materials: list["SpeakerMaterial"] = Relationship(back_populates="speaker")


class SpeakerMaterial(SoftDeleteMixin, table=True):
    __tablename__ = "speaker_materials"
    id: UUID = Field(default_factory=uuid7, primary_key=True)
    speaker_id: UUID = Field(foreign_key="speakers.id")
    title: str = Field(max_length=200)
    description: Optional[str] = Field(default=None)
    file_path: str = Field(max_length=500)
    file_original_name: str = Field(max_length=255)
    file_mime_type: str = Field(max_length=100)
    file_size: int = Field()
    created_at: datetime = Field(default_factory=now_jakarta)

    speaker: Speaker = Relationship(back_populates="materials")


class Certificate(SoftDeleteMixin, table=True):
    __tablename__ = "certificates"
    id: UUID = Field(default_factory=uuid7, primary_key=True)
    code: str = Field(
        default_factory=lambda: f"PBCERT-{now_jakarta().strftime('%Y%m')}-{str(uuid4())[:8].upper()}",
        unique=True, index=True, max_length=30
    )
    user_id: UUID = Field(foreign_key="users.id")
    event_id: UUID = Field(foreign_key="events.id")
    speaker_id: Optional[UUID] = Field(foreign_key="speakers.id", default=None)
    recipient_name: str = Field(max_length=100)
    event_name: str = Field(max_length=200)
    role: str = Field(max_length=50, default="Participant")
    file_path: str = Field(max_length=500)
    issued_by: UUID = Field(foreign_key="users.id")
    created_at: datetime = Field(default_factory=now_jakarta)