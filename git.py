import asyncio
import signal
import logging
import sys
import logging.handlers
from filelock import FileLock, Timeout
from telegram import Bot
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters
from github_manager import GitHubManager
from telegram_handlers import TelegramHandlers
from config import TELEGRAM_TOKEN, GITHUB_TOKEN

# Logging configuration
logging.basicConfig(
    filename='bot.log',
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.INFO)
logger = logging.getLogger(__name__)
logger.addHandler(console_handler)

async def validate_tokens():
    """Validate Telegram and GitHub tokens."""
    try:
        bot = Bot(TELEGRAM_TOKEN)
        await bot.get_me()
        logger.info("Telegram token validated")
    except Exception as e:
        logger.error(f"Invalid Telegram token: {str(e)}")
        sys.exit(1)
    try:
        github = Github(GITHUB_TOKEN)
        github.get_user()
        logger.info("GitHub token validated")
    except Exception as e:
        logger.error(f"Invalid GitHub token: {str(e)}")
        sys.exit(1)

async def main():
    """
    Main function to initialize and run the Telegram bot.
    """
    logger.info("Starting the Telegram bot")
    try:
        await validate_tokens()
        github_manager = GitHubManager(GITHUB_TOKEN)
        telegram_handlers = TelegramHandlers(github_manager)
        app = Application.builder().token(TELEGRAM_TOKEN).build()

        app.add_handler(CommandHandler("start", telegram_handlers.start))
        app.add_handler(CallbackQueryHandler(telegram_handlers.button_callback))
        app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, telegram_handlers.handle_text))
        app.add_handler(MessageHandler(filters.Document.ALL, telegram_handlers.handle_document))

        await app.initialize()
        await app.start()
        await app.updater.start_polling()
        logger.info("Bot started polling")

        await asyncio.Event().wait()  # Wait indefinitely
    except Exception as e:
        logger.error(f"Unexpected error in main: {str(e)}")
        raise
    finally:
        logger.info("Shutting down the bot")
        await app.updater.stop()
        await app.stop()
        await app.shutdown()

if __name__ == "__main__":
    lock_file = "bot.lock"
    lock = FileLock(lock_file, timeout=1)
    try:
        with lock.acquire(timeout=1):
            loop = asyncio.get_event_loop()
            try:
                for sig in (signal.SIGINT, signal.SIGTERM):
                    loop.add_signal_handler(sig, lambda: loop.stop())

                retries = 3
                for attempt in range(retries):
                    try:
                        loop.run_until_complete(main())
                        break
                    except Exception as e:
                        logger.error(f"Attempt {attempt+1} failed: {str(e)}")
                        if attempt < retries - 1:
                            loop.run_until_complete(asyncio.sleep(2 ** attempt))
                        else:
                            raise
            except Exception as e:
                logger.error(f"Error running bot: {str(e)}")
            finally:
                pending = asyncio.all_tasks(loop)
                for task in pending:
                    task.cancel()
                loop.run_until_complete(loop.shutdown_asyncgens())
                loop.close()
                logger.info("Event loop closed")
    except Timeout:
        logger.error("Another instance of the bot is already running!")
        print("Error: Another instance of the bot is already running!")
        sys.exit(1)
    finally:
        if lock.is_locked:
            lock.release()
            logger.info("File lock released")