import os
import logging
import asyncio
from telegram import Update
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler, MessageHandler, filters
from downloader import download_media

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# --- Configuration ---
BOT_TOKEN = os.environ.get("BOT_TOKEN", "8331345003:AAGmMnWIm9dWobekQZImeCdM1Gybs0suxOI")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Sends a welcome message when the command /start is issued."""
    user_first_name = update.effective_user.first_name
    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text=f"Привет, {user_first_name}! 👋\n\n"
             "Я бот-загрузчик медиа. Отправь мне ссылку на видео из Instagram, TikTok или Threads, "
             "и я скачаю его для тебя.\n\n"
             "Просто отправь ссылку! 🚀"
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Sends a help message."""
    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text="Просто отправь мне ссылку на пост в Instagram, TikTok или Threads.\n"
             "Я постараюсь найти видео или фото и отправить его тебе файлом."
    )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles incoming text messages (links)."""
    url = update.message.text.strip()
    
    # Basic validation
    if not (url.startswith("http://") or url.startswith("https://")):
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="Это не похоже на ссылку. Пожалуйста, отправь корректную ссылку, начинающуюся с http:// или https://"
        )
        return

    status_msg = await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text="⏳ Скачиваю медиа... Пожалуйста, подожди."
    )

    try:
        # Run the blocking download function in a separate thread
        loop = asyncio.get_running_loop()
        file_path = await loop.run_in_executor(None, download_media, url)

        if file_path and os.path.exists(file_path):
            # Check file size (Telegram bot API limit is 50MB)
            file_size_mb = os.path.getsize(file_path) / (1024 * 1024)
            
            if file_size_mb > 49:
                await context.bot.edit_message_text(
                    chat_id=update.effective_chat.id,
                    message_id=status_msg.message_id,
                    text=f"❌ Файл слишком большой ({file_size_mb:.1f} MB). Telegram разрешает ботам отправлять файлы только до 50 MB."
                )
                os.remove(file_path)
                return

            await context.bot.edit_message_text(
                chat_id=update.effective_chat.id,
                message_id=status_msg.message_id,
                text="✅ Загрузка завершена! Отправляю файл..."
            )
            
            # Send the video/photo
            with open(file_path, 'rb') as f:
                ext = os.path.splitext(file_path)[1].lower()
                try:
                    if ext in ['.jpg', '.jpeg', '.png', '.webp']:
                        await context.bot.send_photo(chat_id=update.effective_chat.id, photo=f)
                    else:
                        await context.bot.send_video(chat_id=update.effective_chat.id, video=f)
                except Exception as send_error:
                    logger.error(f"Error sending file: {send_error}")
                    await context.bot.send_message(
                        chat_id=update.effective_chat.id,
                        text="❌ Не удалось отправить файл в Telegram. Возможно, формат не поддерживается."
                    )
            
            # Clean up
            os.remove(file_path)
            logger.info(f"File sent and removed: {file_path}")
            
        else:
            await context.bot.edit_message_text(
                chat_id=update.effective_chat.id,
                message_id=status_msg.message_id,
                text="❌ Не удалось скачать видео. Возможно, профиль закрыт, ссылка некорректна или сервис заблокировал доступ."
            )

    except Exception as e:
        logger.error(f"Error handling message: {e}")
        await context.bot.edit_message_text(
            chat_id=update.effective_chat.id,
            message_id=status_msg.message_id,
            text="❌ Произошла ошибка при обработке. Попробуй другую ссылку."
        )

if __name__ == '__main__':
    if BOT_TOKEN == "YOUR_BOT_TOKEN_HERE":
        print("ERROR: Please set your BOT_TOKEN in the script or environment variable.")
    else:
        application = ApplicationBuilder().token(BOT_TOKEN).build()

        # Handlers
        start_handler = CommandHandler('start', start)
        help_handler = CommandHandler('help', help_command)
        message_handler = MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message)

        application.add_handler(start_handler)
        application.add_handler(help_handler)
        application.add_handler(message_handler)

        print("Bot is running...")
        application.run_polling()
