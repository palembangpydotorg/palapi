from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters

from .start import start_command, handle_start_callbacks
from .register import register_conv
from .admin import show_admin_menu, handle_admin_callback, handle_admin_text_steps, handle_promote_command
from .staff import show_staff_menu, handle_staff_callback
from .member import show_general_menu, handle_member_callback
from .speaker import show_speaker_menu, handle_speaker_callback, handle_speaker_text_steps, handle_speaker_document
from .certificate import generate_user_certificate

def setup_handlers(app: Application):
    app.add_handler(register_conv)

    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("admin", show_admin_menu))
    app.add_handler(CommandHandler("staff", show_staff_menu))
    app.add_handler(CommandHandler("menu", show_general_menu))
    app.add_handler(CommandHandler("speaker", show_speaker_menu))
    app.add_handler(CommandHandler("cert", generate_user_certificate))
    app.add_handler(CommandHandler("promote", handle_promote_command))

    app.add_handler(CallbackQueryHandler(handle_start_callbacks, pattern="^(tentang|menu_utama)$"))
    app.add_handler(CallbackQueryHandler(handle_admin_callback, pattern="^adm_"))
    app.add_handler(CallbackQueryHandler(handle_staff_callback, pattern="^staff_"))
    app.add_handler(CallbackQueryHandler(handle_member_callback, pattern="^member_"))
    app.add_handler(CallbackQueryHandler(handle_speaker_callback, pattern="^speaker_"))

    app.add_handler(MessageHandler(filters.Document.ALL & ~filters.COMMAND, handle_speaker_document))

    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_admin_text_steps))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_speaker_text_steps))
