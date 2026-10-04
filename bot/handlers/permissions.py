from cachetools import TTLCache
from telegram import Update
from telegram.ext import ContextTypes
from sqlmodel import Session, select
from database import engine
from models import User

role_cache = TTLCache(maxsize=1000, ttl=300)

async def get_user_role(telegram_id: str) -> dict:
    id_str = str(telegram_id)
    if id_str in role_cache:
        return role_cache[id_str]

    with Session(engine) as db:
        user = db.exec(select(User).where(User.telegram_id == id_str, User.deleted_at == None)).first()
        if not user:
            role = {"is_admin": False, "is_staff": False}
        else:
            role = {"is_admin": bool(user.is_admin), "is_staff": bool(user.is_staff)}
        
        role_cache[id_str] = role
        return role

def require_admin(handler):
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
        userId = update.effective_user.id if update.effective_user else None
        if not userId:
            return

        role = await get_user_role(str(userId))
        if not role["is_admin"]:
            if update.callback_query:
                await update.callback_query.answer(text="❌ Perintah ini khusus Super Admin!", show_alert=True)
            else:
                await update.message.reply_text("❌ Perintah ini khusus Super Admin.")
            return
        return await handler(update, context, *args, **kwargs)
    return wrapper

def require_staff(handler):
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
        userId = update.effective_user.id if update.effective_user else None
        if not userId:
            return

        role = await get_user_role(str(userId))
        if not role["is_admin"] and not role["is_staff"]:
            if update.callback_query:
                await update.callback_query.answer(text="❌ Perintah ini khusus Staff / Admin!", show_alert=True)
            else:
                await update.message.reply_text("❌ Perintah ini khusus Staff / Admin.")
            return
        return await handler(update, context, *args, **kwargs)
    return wrapper

def invalidate_role_cache(telegram_id):
    if telegram_id:
        role_cache.pop(str(telegram_id), None)
