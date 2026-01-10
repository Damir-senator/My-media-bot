import os
import logging
import asyncio
from telegram import Update
from telegram.constants import ChatAction
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler, MessageHandler, filters
from telegram.error import TimedOut
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
             "Я бот-загрузчик медиа. Отправь мне ссылку на видео из TikTok или YouTube Shorts, "
             "и я скачаю его для тебя.\n\n"
             "Просто отправь ссылку! 🚀"
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Sends a help message."""
    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text="Просто отправь мне ссылку на видео.\n"
             "Я постараюсь найти видео и отправить его тебе файлом."
    )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles incoming text messages (links)."""
    url = update.message.text.strip()
    
    # Basic validation
    if not (url.startswith("http://") or url.startswith("https://")):
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="Это не похоже на ссылку. Пожалуйста, отправь корректную ссылку, начинающуюся с http:// или https://",
            reply_to_message_id=update.message.message_id
        )
        return

    status_msg = await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text="⏳ Скачиваю медиа... Пожалуйста, подожди.",
        reply_to_message_id=update.message.message_id
    )

    file_path = None
    try:
        # Run the blocking download function in a separate thread
        loop = asyncio.get_running_loop()
        file_path = await loop.run_in_executor(None, download_media, url)

        if not file_path or not os.path.exists(file_path):
            await context.bot.edit_message_text(
                chat_id=update.effective_chat.id,
                message_id=status_msg.message_id,
                text="❌ Не удалось скачать видео. Возможно, профиль закрыт или ссылка некорректна."
            )
            return

        # Check file size (Telegram bot API limit is 50MB)
        file_size_mb = os.path.getsize(file_path) / (1024 * 1024)
        
        if file_size_mb > 49:
            await context.bot.edit_message_text(
                chat_id=update.effective_chat.id,
                message_id=status_msg.message_id,
                text=f"❌ Файл слишком большой ({file_size_mb:.1f} MB). Telegram разрешает ботам отправлять файлы только до 50 MB."
            )
            return # file_path will be cleaned up in finally block

        await context.bot.edit_message_text(
            chat_id=update.effective_chat.id,
            message_id=status_msg.message_id,
            text="✅ Загрузка завершена! Отправляю файл..."
        )
        
        # Send the video/photo
        try:
            # Show "uploading video..." status
            await context.bot.send_chat_action(chat_id=update.effective_chat.id, action=ChatAction.UPLOAD_VIDEO)
            
            with open(file_path, 'rb') as f:
                ext = os.path.splitext(file_path)[1].lower()
                if ext in ['.jpg', '.jpeg', '.png', '.webp']:
                    await context.bot.send_photo(
                        chat_id=update.effective_chat.id, 
                        photo=f,
                        reply_to_message_id=update.message.message_id,
                        read_timeout=60, 
                        write_timeout=60,
                        connect_timeout=60
                    )
                else:
                    await context.bot.send_video(
                        chat_id=update.effective_chat.id, 
                        video=f,
                        reply_to_message_id=update.message.message_id,
                        read_timeout=60, 
                        write_timeout=60,
                        connect_timeout=60
                    )
            
            # If successful, delete the status message to keep chat clean
            try:
                await context.bot.delete_message(chat_id=update.effective_chat.id, message_id=status_msg.message_id)
            except Exception:
                pass # Ignore if already deleted

        except TimedOut:
            logger.warning("Telegram TimedOut error occurred, but file might have been sent.")
        except Exception as send_error:
            logger.error(f"Error sending file: {send_error}")
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text="❌ Не удалось отправить файл в Telegram. Возможно, формат не поддерживается.",
                reply_to_message_id=update.message.message_id
            )
        
    except Exception as e:
        logger.error(f"Error handling message: {e}")
        try:
            await context.bot.edit_message_text(
                chat_id=update.effective_chat.id,
                message_id=status_msg.message_id,
                text="❌ Произошла ошибка при обработке. Попробуй другую ссылку."
            )
        except Exception:
            pass
    finally:
        # Robust cleanup: Always remove the file, no matter what happened
        if file_path and os.path.exists(file_path):
            try:
                os.remove(file_path)
                logger.info(f"File cleaned up: {file_path}")
            except Exception as cleanup_error:
                logger.error(f"Failed to remove file {file_path}: {cleanup_error}")

if __name__ == '__main__':
    if BOT_TOKEN == "YOUR_BOT_TOKEN_HERE":
        print("ERROR: Please set your BOT_TOKEN in the script or environment variable.")
    else:
        # Increase connection pool size and timeouts for better stability
        application = ApplicationBuilder().token(BOT_TOKEN).read_timeout(60).write_timeout(60).build()

        # Handlers
        start_handler = CommandHandler('start', start)
        help_handler = CommandHandler('help', help_command)
        message_handler = MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message)

        application.add_handler(start_handler)
        application.add_handler(help_handler)
        application.add_handler(message_handler)

        print("Bot is running...")
        application.run_polling()
