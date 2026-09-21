from contextlib import asynccontextmanager
from uuid import UUID
from typing import Annotated
from fastapi import FastAPI, HTTPException, Query, Depends, UploadFile, File, Form, Request
from sqlmodel import Session
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

from database import init_db, get_session
import schemas
import crud


limiter = Limiter(key_func=get_remote_address)
DB = Annotated[Session, Depends(get_session)]


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(
    title="PalembangPy Community API",
    version="1.0.0",
    description="User, Partner, Event, Speaker, Certificate & File Management",
    lifespan=lifespan
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)


# --- User Endpoints ---
@app.get("/v1/users", response_model=list[schemas.UserResponse])
@limiter.limit("60/minute")
def list_users(
    request: Request,
    db: DB,
    include_deleted: bool = Query(False)
):
    return crud.get_users(db, include_deleted=include_deleted)


@app.post("/v1/users", response_model=schemas.UserCreateResponse, status_code=201)
@limiter.limit("20/minute")
def create_user(
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
    request: Request,
    user_id: UUID,
    db: DB,
    include_deleted: bool = Query(False)
):
    user = crud.get_user(db, user_id, include_deleted=include_deleted)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user


@app.get("/v1/users/telegram/{telegram_id}", response_model=schemas.UserResponse)
@limiter.limit("30/minute")
def get_user_by_telegram_id(
    request: Request,
    telegram_id: str,
    db: DB
):
    user = crud.get_user_by_telegram(db, telegram_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user


@app.patch("/v1/users/{user_id}", response_model=schemas.UserResponse)
@limiter.limit("30/minute")
def update_user_info(
    request: Request,
    user_id: UUID,
    data: schemas.UserUpdate,
    db: DB
):
    user = crud.get_user(db, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return crud.update_user(db, user, data.model_dump(exclude_unset=True))


@app.delete("/v1/users/{user_id}/soft")
@limiter.limit("15/minute")
def soft_delete_user_account(
    request: Request,
    user_id: UUID,
    db: DB
):
    user = crud.get_user(db, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    crud.soft_delete_user(db, user)
    return {"status": "success", "message": "Account soft deleted"}


@app.delete("/v1/users/{user_id}/hard")
@limiter.limit("10/minute")
def hard_delete_user_account(
    request: Request,
    user_id: UUID,
    db: DB
):
    user = crud.get_user(db, user_id, include_deleted=True)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    crud.hard_delete_user(db, user)
    return {"status": "success", "message": "Account permanently deleted"}


@app.get("/v1/users/{user_id}/certificates", response_model=list[schemas.CertificateResponse])
@limiter.limit("30/minute")
def list_user_certificates(
    request: Request,
    user_id: UUID,
    db: DB
):
    return crud.get_certificates_by_user(db, user_id)


# --- Partner Endpoints ---
@app.get("/v1/partners", response_model=list[schemas.PartnerResponse])
@limiter.limit("60/minute")
def list_partners(
    request: Request,
    db: DB,
    include_deleted: bool = Query(False)
):
    return crud.get_partners(db, include_deleted=include_deleted)


@app.post("/v1/partners", response_model=schemas.PartnerResponse, status_code=201)
@limiter.limit("20/minute")
def register_partner(
    request: Request,
    data: schemas.PartnerCreate,
    db: DB
):
    return crud.create_partner(db, data.model_dump())


@app.get("/v1/partners/{partner_id}", response_model=schemas.PartnerResponse)
@limiter.limit("60/minute")
def get_partner_info(
    request: Request,
    partner_id: UUID,
    db: DB,
    include_deleted: bool = Query(False)
):
    partner = crud.get_partner(db, partner_id, include_deleted=include_deleted)
    if not partner:
        raise HTTPException(status_code=404, detail="Partner not found")
    return partner


@app.patch("/v1/partners/{partner_id}", response_model=schemas.PartnerResponse)
@limiter.limit("30/minute")
def update_partner_info(
    request: Request,
    partner_id: UUID,
    data: schemas.PartnerUpdate,
    db: DB
):
    partner = crud.get_partner(db, partner_id)
    if not partner:
        raise HTTPException(status_code=404, detail="Partner not found")
    return crud.update_partner(db, partner, data.model_dump(exclude_unset=True))


@app.delete("/v1/partners/{partner_id}/soft")
@limiter.limit("15/minute")
def soft_delete_partner_info(
    request: Request,
    partner_id: UUID,
    db: DB
):
    partner = crud.get_partner(db, partner_id)
    if not partner:
        raise HTTPException(status_code=404, detail="Partner not found")
    crud.soft_delete_partner(db, partner)
    return {"status": "success", "message": "Partner soft deleted"}


@app.delete("/v1/partners/{partner_id}/hard")
@limiter.limit("10/minute")
def hard_delete_partner_info(
    request: Request,
    partner_id: UUID,
    db: DB
):
    partner = crud.get_partner(db, partner_id, include_deleted=True)
    if not partner:
        raise HTTPException(status_code=404, detail="Partner not found")
    crud.hard_delete_partner(db, partner)
    return {"status": "success", "message": "Partner permanently deleted"}


# --- Event Endpoints ---
@app.get("/v1/events", response_model=list[schemas.EventResponse])
@limiter.limit("60/minute")
def list_events(
    request: Request,
    db: DB,
    include_deleted: bool = Query(False)
):
    return crud.get_events(db, include_deleted=include_deleted)


@app.post("/v1/events", response_model=schemas.EventResponse, status_code=201)
@limiter.limit("20/minute")
def create_event_record(
    request: Request,
    data: schemas.EventCreate,
    db: DB
):
    return crud.create_event(db, data.model_dump())


@app.get("/v1/events/{event_id}", response_model=schemas.EventResponse)
@limiter.limit("60/minute")
def get_event_detail(
    request: Request,
    event_id: UUID,
    db: DB,
    include_deleted: bool = Query(False)
):
    event = crud.get_event(db, event_id, include_deleted=include_deleted)
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")
    return event


@app.patch("/v1/events/{event_id}", response_model=schemas.EventResponse)
@limiter.limit("30/minute")
def update_event_detail(
    request: Request,
    event_id: UUID,
    data: schemas.EventUpdate,
    db: DB
):
    event = crud.get_event(db, event_id)
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")
    return crud.update_event(db, event, data.model_dump(exclude_unset=True))


@app.delete("/v1/events/{event_id}/soft")
@limiter.limit("15/minute")
def soft_delete_event_record(
    request: Request,
    event_id: UUID,
    db: DB
):
    event = crud.get_event(db, event_id)
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")
    crud.soft_delete_event(db, event)
    return {"status": "success", "message": "Event soft deleted"}


@app.delete("/v1/events/{event_id}/hard")
@limiter.limit("10/minute")
def hard_delete_event_record(
    request: Request,
    event_id: UUID,
    db: DB
):
    event = crud.get_event(db, event_id, include_deleted=True)
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")
    crud.hard_delete_event(db, event)
    return {"status": "success", "message": "Event permanently deleted"}


@app.post("/v1/events/{event_id}/generate-certificates", status_code=201)
@limiter.limit("10/minute")
def generate_certificates_for_event(
    request: Request,
    event_id: UUID,
    data: schemas.CertificateGenerate,
    db: DB
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
    request: Request,
    db: DB,
    include_deleted: bool = Query(False)
):
    return crud.get_speakers(db, include_deleted=include_deleted)


@app.post("/v1/speakers", response_model=schemas.SpeakerResponse, status_code=201)
@limiter.limit("20/minute")
def register_speaker(
    request: Request,
    data: schemas.SpeakerCreate,
    db: DB
):
    return crud.create_speaker(db, data.model_dump())


@app.get("/v1/speakers/{speaker_id}", response_model=schemas.SpeakerResponse)
@limiter.limit("60/minute")
def get_speaker_detail(
    request: Request,
    speaker_id: UUID,
    db: DB,
    include_deleted: bool = Query(False)
):
    speaker = crud.get_speaker(db, speaker_id, include_deleted=include_deleted)
    if not speaker:
        raise HTTPException(status_code=404, detail="Speaker not found")
    return speaker


@app.patch("/v1/speakers/{speaker_id}", response_model=schemas.SpeakerResponse)
@limiter.limit("30/minute")
def update_speaker_detail(
    request: Request,
    speaker_id: UUID,
    data: schemas.SpeakerUpdate,
    db: DB
):
    speaker = crud.get_speaker(db, speaker_id)
    if not speaker:
        raise HTTPException(status_code=404, detail="Speaker not found")
    return crud.update_speaker(db, speaker, data.model_dump(exclude_unset=True))


@app.delete("/v1/speakers/{speaker_id}/soft")
@limiter.limit("15/minute")
def soft_delete_speaker_record(
    request: Request,
    speaker_id: UUID,
    db: DB
):
    speaker = crud.get_speaker(db, speaker_id)
    if not speaker:
        raise HTTPException(status_code=404, detail="Speaker not found")
    crud.soft_delete_speaker(db, speaker)
    return {"status": "success", "message": "Speaker soft deleted"}


@app.delete("/v1/speakers/{speaker_id}/hard")
@limiter.limit("10/minute")
def hard_delete_speaker_record(
    request: Request,
    speaker_id: UUID,
    db: DB
):
    speaker = crud.get_speaker(db, speaker_id, include_deleted=True)
    if not speaker:
        raise HTTPException(status_code=404, detail="Speaker not found")
    crud.hard_delete_speaker(db, speaker)
    return {"status": "success", "message": "Speaker permanently deleted"}


@app.post("/v1/speakers/{speaker_id}/materials", status_code=201)
@limiter.limit("15/minute")
def upload_speaker_material(
    request: Request,
    speaker_id: UUID,
    title: Annotated[str, Form()],
    db: DB,
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


# --- Certificate Verification ---
@app.get("/v1/certificates/verify/{code}", response_model=schemas.CertificateResponse)
@limiter.limit("120/minute")
def verify_certificate(
    request: Request,
    code: str,
    db: DB
):
    certificate = crud.get_certificate_by_code(db, code)
    if not certificate:
        raise HTTPException(status_code=404, detail="Certificate not found or revoked")
    return certificate


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="127.0.0.1", port=5174, reload=True)