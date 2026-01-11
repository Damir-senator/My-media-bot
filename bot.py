import os
import logging
from telegram import Update, InputFile
from telegram.constants import ChatAction
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

from downloader import download_media

# -------------------- CONFIG --------------------

BOT_TOKEN = os.getenv("BOT_TOKEN")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# -------------------- HANDLERS --------------------

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Отправь ссылку на TikTok — я скачаю видео."
    )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text:
        return

    url = update.message.text.strip()

    if "tiktok.com" not in url:
        await update.message.reply_text(
            "Пока поддерживается только TikTok."
        )
        return

    user = update.effective_user
    logger.info(
        "Download request | user_id=%s username=%s url=%s",
        user.id if user else None,
        user.username if user else None,
        url,
    )

    await context.bot.send_chat_action(
        chat_id=update.effective_chat.id,
        action=ChatAction.UPLOAD_DOCUMENT,
    )

    file_path = None

    try:
        # Скачиваем видео
        file_path = download_media(url)

        if not file_path or not os.path.exists(file_path):
            raise RuntimeError("Файл не был создан")

        # ❗ КЛЮЧЕВОЙ ФИКС:
        # Отправляем КАК ФАЙЛ, а не как video
        await update.message.reply_document(
            document=InputFile(file_path),
            filename="video.mp4"
        )

        logger.info("Video sent as document successfully")

    except Exception:
        logger.exception("Send error")
        await update.message.reply_text(
            "Не удалось отправить видео. Попробуй другую ссылку."
        )

    finally:
        if file_path and os.path.exists(file_path):
            try:
                os.remove(file_path)
                logger.info("Temp file removed")
            except Exception:
                logger.exception("Failed to remove temp file")

# -------------------- MAIN --------------------

def main():
    if not BOT_TOKEN:
        logger.error("BOT_TOKEN is not set — bot will not start")
        return

    application = (
        ApplicationBuilder()
        .token(BOT_TOKEN)
        .concurrent_updates(False)
        .read_timeout(60)
        .write_timeout(60)
        .build()
    )

    application.add_handler(CommandHandler("start", start))
    application.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message)
    )

    logger.info("Bot started")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()