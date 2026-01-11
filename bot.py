import os
import logging
from telegram import Update
from telegram.constants import ChatAction
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

from downloader import download_media

# ---------------- CONFIG ----------------

BOT_TOKEN = os.getenv("BOT_TOKEN")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# ---------------- HANDLERS ----------------

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

    await context.bot.send_chat_action(
        chat_id=update.effective_chat.id,
        action=ChatAction.UPLOAD_VIDEO,
    )

    file_path = None

    try:
        # 1. Скачиваем видео
        file_path = download_media(url)

        if not file_path or not os.path.exists(file_path):
            raise RuntimeError("Файл не найден после загрузки")

        # 2. ОТПРАВЛЯЕМ КАК ВИДЕО (КЛЮЧ!)
        with open(file_path, "rb") as video:
            await update.message.reply_video(
                video=video,
                supports_streaming=True
            )

        logger.info("Video sent successfully")

    except Exception as e:
        logger.exception("Send error")
        await update.message.reply_text(
            "Не удалось отправить видео. Попробуй другую ссылку."
        )

    finally:
        if file_path and os.path.exists(file_path):
            try:
                os.remove(file_path)
            except Exception:
                logger.exception("Failed to remove temp file")

# ---------------- MAIN ----------------

def main():
    if not BOT_TOKEN:
        logger.error("BOT_TOKEN is not set")
        return

    app = (
        ApplicationBuilder()
        .token(BOT_TOKEN)
        .read_timeout(60)
        .write_timeout(60)
        .build()
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message)
    )

    logger.info("Bot started")
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()