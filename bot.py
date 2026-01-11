import os
import time
import logging
from collections import defaultdict, deque
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

# ---------------- RATE LIMIT ----------------
# 5 успешных загрузок за 10 минут

RATE_LIMIT = 5
RATE_WINDOW = 600  # секунд

user_requests = defaultdict(deque)

def register_request(user_id: int) -> bool:
    now = time.time()
    queue = user_requests[user_id]

    while queue and queue[0] < now - RATE_WINDOW:
        queue.popleft()

    if len(queue) >= RATE_LIMIT:
        return False

    queue.append(now)
    return True

# ---------------- HELPERS ----------------

def get_user_name(update: Update) -> str:
    user = update.effective_user
    if not user:
        return "друг"
    return user.first_name or user.username or "друг"

# ---------------- HANDLERS ----------------

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    name = get_user_name(update)

    await update.message.reply_text(
        f"Привет, {name}! 👋\n"
        "Отправь ссылку на видео из TikTok — я скачаю его для тебя."
    )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text:
        return

    user = update.effective_user
    if not user:
        return

    url = update.message.text.strip()

    if "tiktok.com" not in url:
        await update.message.reply_text(
            "Пока поддерживается только TikTok."
        )
        return

    # 🔒 RATE LIMIT
    if not register_request(user.id):
        await update.message.reply_text(
            "⏳ Слишком много запросов.\n"
            "Лимит: 5 видео за 10 минут.\n"
            "Попробуй позже."
        )
        return

    logger.info(
        "Download request | user_id=%s username=%s url=%s",
        user.id,
        user.username,
        url,
    )

    await context.bot.send_chat_action(
        chat_id=update.effective_chat.id,
        action=ChatAction.UPLOAD_VIDEO,
    )

    file_path = None

    try:
        file_path = download_media(url)

        if not file_path or not os.path.exists(file_path):
            raise RuntimeError("Файл не найден")

        # ✅ Отправляем видео
        with open(file_path, "rb") as video:
            await update.message.reply_video(
                video=video,
                supports_streaming=True
            )

        # ✅ Подпись автора после успешной отправки
        await update.message.reply_text(
            "Автор бота: Damir Kabdulla (@KING_TRAFF)"
        )

        logger.info("Video sent successfully")

    except Exception:
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