import os
import time
import logging
from collections import defaultdict, deque
from typing import List

from telegram import Update, InputMediaPhoto
from telegram.constants import ChatAction
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

from downloader import download_media

BOT_TOKEN = os.getenv("BOT_TOKEN")
DOWNLOAD_DIR = "/app/downloads"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# ---------- RATE LIMIT ----------
RATE_LIMIT = 5
RATE_WINDOW = 600  # 10 минут
user_requests = defaultdict(deque)

def is_rate_limited(user_id: int) -> bool:
    now = time.time()
    q = user_requests[user_id]

    while q and q[0] < now - RATE_WINDOW:
        q.popleft()

    if len(q) >= RATE_LIMIT:
        return True

    q.append(now)
    return False

# ---------- HANDLERS ----------

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    name = user.first_name or user.username or "друг"

    await update.message.reply_text(
        f"Привет, {name}! 👋\n\n"
        "Отправь ссылку на TikTok — я скачаю видео или фото для тебя."
    )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text:
        return

    user = update.effective_user
    url = update.message.text.strip()

    if "tiktok.com" not in url:
        await update.message.reply_text("Поддерживается только TikTok.")
        return

    if is_rate_limited(user.id):
        await update.message.reply_text(
            "⏳ Лимит: 5 загрузок за 10 минут.\nПопробуй позже."
        )
        return

    files_to_cleanup: List[str] = []

    try:
        result = download_media(url)

        # ---------- VIDEO ----------
        if result["type"] == "video":
            await context.bot.send_chat_action(
                chat_id=update.effective_chat.id,
                action=ChatAction.UPLOAD_VIDEO,
            )

            video_path = result["path"]
            files_to_cleanup.append(video_path)

            with open(video_path, "rb") as f:
                await update.message.reply_video(
                    video=f,
                    supports_streaming=True,
                )

        # ---------- IMAGES (CAROUSEL) ----------
        elif result["type"] == "images":
            await context.bot.send_chat_action(
                chat_id=update.effective_chat.id,
                action=ChatAction.UPLOAD_PHOTO,
            )

            media = []
            opened_files = []

            for path in result["paths"][:10]:
                f = open(path, "rb")
                opened_files.append(f)
                files_to_cleanup.append(path)
                media.append(InputMediaPhoto(f))

            await update.message.reply_media_group(media)

            # закрываем файлы
            for f in opened_files:
                f.close()

        else:
            raise RuntimeError(f"Unknown media type: {result}")

        await update.message.reply_text(
            "Автор бота: Damir Kabdulla (@KING_TRAFF)"
        )

    except Exception:
        logger.exception("Send error")
        await update.message.reply_text(
            "Не удалось отправить медиа. Попробуй другую ссылку."
        )

    finally:
        for path in files_to_cleanup:
            try:
                if os.path.exists(path):
                    os.remove(path)
            except Exception:
                logger.warning("Failed to cleanup file: %s", path)

# ---------- MAIN ----------

def main():
    if not BOT_TOKEN:
        raise RuntimeError("BOT_TOKEN is not set")

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
    app.run_polling()

if __name__ == "__main__":
    main()