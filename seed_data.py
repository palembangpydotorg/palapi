from sqlmodel import Session
from database import engine
from crud import create_user


def seed_all():
    with Session(engine) as db:
        try:
            create_user(db, {
                "name": "PalembangPy Admin",
                "telegram_id": "admin_palpy_001",
                "bio": "Community Administrator",
                "is_admin": True,
                "is_staff": True
            })
            print("✅ Seed data inserted successfully")
        except Exception as exc:
            print(f"ℹ️ Seed skipped: {exc}")


if __name__ == "__main__":
    seed_all()