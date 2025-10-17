# bot.py 
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
)
import logging
from logging.handlers import RotatingFileHandler
from src.utils import load_config
from src.db import init_db, get_configs_by_protocol, cleanup_old_configs, clear_all_configs, get_db_connection
from src.link_collector import collect_v2ray_links
from src.proxy_collector import collect_proxies
from src.proxy_tester import test_all_proxies
from src.stats import get_stats
import asyncio
from dotenv import load_dotenv
import sqlite3

# تنظیم لاگ‌گیری مرکزی با چرخش فایل
handler = RotatingFileHandler("logs/bot.log", maxBytes=1000000, backupCount=5)
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO,
    handlers=[handler, logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

# لود متغیرهای محیطی
load_dotenv()
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")

def is_admin(user_id):
    """بررسی اینکه آیا کاربر ادمین است یا خیر"""
    try:
        config = load_config()
        return user_id in config["telegram"]["admin_ids"]
    except Exception as e:
        logger.error(f"خطا در بررسی ادمین: {e}")
        return False

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """دستور شروع ربات با منوی گرافیکی"""
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("فقط ادمین‌ها می‌تونن از این ربات استفاده کنن! 🚫\nتماس با ادمین: @Savior_128")
        return
    keyboard = [
        [
            InlineKeyboardButton("انتخاب پروتکل 📡", callback_data="cmd_protocol"),
            InlineKeyboardButton("به‌روزرسانی کانفیگ‌ها 🔄", callback_data="cmd_update"),
        ],
        [
            InlineKeyboardButton("دریافت پروکسی‌ها 🌐", callback_data="cmd_proxies"),
            InlineKeyboardButton("به‌روزرسانی پروکسی‌ها 🔄", callback_data="cmd_update_proxies"),
        ],
        [
            InlineKeyboardButton("تست پروکسی‌ها 🧪", callback_data="cmd_test_proxies"),
            InlineKeyboardButton("آمار کانفیگ‌ها 📊", callback_data="cmd_stats"),
        ],
        [
            InlineKeyboardButton("راهنما ❓", callback_data="cmd_help"),
            InlineKeyboardButton("پاک کردن همه کانفیگ‌ها 🗑️", callback_data="cmd_clear"),
        ],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        "به ربات کانفیگ V2Ray و پروکسی خوش اومدی! 😊\nیکی از گزینه‌ها رو انتخاب کن:",
        reply_markup=reply_markup
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """دستور نمایش راهنمای ربات"""
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("فقط ادمین‌ها می‌تونن از این ربات استفاده کنن! 🚫\nتماس با ادمین: @Savior_128")
        return
    help_text = (
        "📋 راهنمای دستورات ربات:\n\n"
        "/start - شروع کار با ربات و نمایش منوی اصلی\n"
        "/help - نمایش این راهنما\n"
        "/protocol - انتخاب پروتکل و دریافت کانفیگ‌ها\n"
        "/stats - نمایش آمار کانفیگ‌ها و پروکسی‌ها\n"
        "/clear - پاک کردن همه کانفیگ‌ها و پروکسی‌ها (نیاز به تأیید)\n\n"
        "⚠️ از منوی گرافیکی برای دریافت، به‌روزرسانی یا تست پروکسی‌ها استفاده کن!\n"
        "⚠️ فقط ادمین‌ها می‌تونن از این دستورات استفاده کنن!"
    )
    await update.message.reply_text(help_text)

async def protocol(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """دستور انتخاب پروتکل"""
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("فقط ادمین‌ها می‌تونن از این ربات استفاده کنن! 🚫\nتماس با ادمین: @Savior_128")
        return
    protocols = ["vmess", "vless", "hysteria2"]
    keyboard = [[InlineKeyboardButton(protocol, callback_data=f"protocol_{protocol}") for protocol in protocols]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("یه پروتکل انتخاب کن:", reply_markup=reply_markup)

async def clear(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """دستور پاک کردن همه کانفیگ‌ها و پروکسی‌ها با تأیید"""
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("فقط ادمین‌ها می‌تونن از این ربات استفاده کنن! 🚫\nتماس با ادمین: @Savior_128")
        return
    keyboard = [
        [InlineKeyboardButton("بله، پاک کن 🗑️", callback_data="confirm_clear")],
        [InlineKeyboardButton("خیر، لغو کن ❌", callback_data="cancel_clear")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        "مطمئنی می‌خوای همه کانفیگ‌ها و پروکسی‌ها رو پاک کنی؟ این کار قابل بازگشت نیست! 😳",
        reply_markup=reply_markup
    )

async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """دستور نمایش آمار دیتابیس"""
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("فقط ادمین‌ها می‌تونن از این ربات استفاده کنن! 🚫\nتماس با ادمین: @Savior_128")
        return
    config = load_config()
    db_path = config["database"]["DB_FILE"]
    message = get_stats(db_path)
    if "خطا" in message:
        await update.message.reply_text("خطایی در دریافت آمار رخ داد! 😓")
    else:
        await update.message.reply_text(message)

async def protocol_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """مدیریت انتخاب پروتکل و دستورات منوی اصلی"""
    file_path = None
    try:
        if not is_admin(update.effective_user.id):
            await update.callback_query.answer("فقط ادمین‌ها می‌تونن از این ربات استفاده کنن! 🚫")
            return

        query = update.callback_query
        await query.answer()
        command = query.data
        config = load_config()
        db_path = config["database"]["DB_FILE"]
        max_configs = config["limits"]["max_configs_per_protocol"]

        if command == "cmd_protocol":
            protocols = ["vmess", "vless", "hysteria2"]
            keyboard = [[InlineKeyboardButton(protocol, callback_data=f"protocol_{protocol}") for protocol in protocols]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.message.reply_text("یه پروتکل انتخاب کن:", reply_markup=reply_markup)
            return
        elif command == "cmd_update":
            await query.message.reply_text("در حال به‌روزرسانی کانفیگ‌ها... ⏳")
            await collect_v2ray_links(db_path)
            await query.message.reply_text("کانفیگ‌ها با موفقیت به‌روزرسانی شدن! 🎉")
            return
        elif command == "cmd_proxies":
            file_path = "cache/proxies.txt"
            if not os.path.exists(file_path):
                await query.message.reply_text("هیچ پروکسی‌ای پیدا نشد! 😕")
                return
            with open(file_path, "rb") as f:
                await query.message.reply_document(document=f, caption="لیست پروکسی‌های HTTP 🌐")
            return
        elif command == "cmd_update_proxies":
            await query.message.reply_text("در حال به‌روزرسانی پروکسی‌ها... ⏳")
            file_path, count = await collect_proxies(db_path)
            await query.message.reply_text(f"پروکسی‌ها با موفقیت به‌روزرسانی شدند! {count} پروکسی جمع‌آوری شد. 🎉")
            return
        elif command == "cmd_test_proxies":
            await query.message.reply_text("در حال تست پروکسی‌ها... ⏳")
            results = await test_all_proxies(db_path, use_file=True)
            valid_count = len([r for r in results if r["status"] == "active"])
            file_path = "cache/valid_proxies.txt"
            if valid_count > 0 and os.path.exists(file_path):
                with open(file_path, "rb") as f:
                    await query.message.reply_document(document=f, caption=f"تست کامل شد! {valid_count} پروکسی معتبر. 🧪")
            else:
                await query.message.reply_text("هیچ پروکسی معتبری یافت نشد! 😕")
            return
        elif command == "cmd_stats":
            message = get_stats(db_path)
            await query.message.reply_text(message)
            return
        elif command == "cmd_help":
            help_text = ( ... )  # همان متن help
            await query.message.reply_text(help_text)
            return
        elif command == "cmd_clear":
            keyboard = [ ... ]  # همان clear
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.message.reply_text("مطمئنی؟", reply_markup=reply_markup)
            return
        elif command == "confirm_clear":
            clear_all_configs(db_path)
            await query.message.reply_text("پاک شد! 🗑️")
            return
        elif command == "cancel_clear":
            await query.message.reply_text("لغو شد! 😊")
            return

        protocol = command.replace("protocol_", "")
        configs = get_configs_by_protocol(db_path, protocol, max_configs)
        if not configs:
            await query.message.reply_text(f"هیچ کانفیگی برای {protocol} پیدا نشد! 😕")
            return

        file_path = f"cache/{protocol}_configs.txt"
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        with open(file_path, "w", encoding="utf-8") as f:
            for config in configs:
                f.write(config + "\n")

        with open(file_path, "rb") as f:
            await query.message.reply_document(document=f, caption=f"کانفیگ‌های {protocol} ({len(configs)} تا) 🚀")
    except Exception as e:
        logger.error(f"خطا: {e}")
        await query.message.reply_text("خطایی رخ داد! 😓")
    finally:
        if file_path and os.path.exists(file_path):
            os.remove(file_path)
            logger.info(f"فایل موقت حذف شد: {file_path}")

async def update(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return
    config = load_config()
    db_path = config["database"]["DB_FILE"]
    await update.message.reply_text("در حال به‌روزرسانی... ⏳")
    await collect_v2ray_links(db_path)
    await update.message.reply_text("به‌روزرسانی شد! 🎉")

async def update_configs(context: ContextTypes.DEFAULT_TYPE):
    try:
        config = load_config()
        db_path = config["database"]["DB_FILE"]
        cleanup_old_configs(db_path, config["schedule"]["cleanup_interval"])
        await collect_v2ray_links(db_path)
        await collect_proxies(db_path)
        logger.info("به‌روزرسانی دوره‌ای کامل شد.")
    except Exception as e:
        logger.error(f"خطا در job: {e}")

def main():
    if not TELEGRAM_TOKEN:
        logger.error("TELEGRAM_TOKEN تنظیم نشده!")
        sys.exit(1)

    config = load_config()
    db_path = config["database"]["DB_FILE"]
    init_db(db_path)

    app = Application.builder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("protocol", protocol))
    app.add_handler(CommandHandler("update", update))
    app.add_handler(CommandHandler("stats", stats))
    app.add_handler(CommandHandler("clear", clear))
    app.add_handler(CallbackQueryHandler(protocol_callback, pattern="^(protocol_|cmd_|confirm_clear|cancel_clear)"))

    app.job_queue.run_repeating(
        update_configs,
        interval=config["schedule"]["update_interval"],
        first=0
    )

    logger.info("ربات شروع شد...")
    app.run_polling()

if __name__ == "__main__":
    main()